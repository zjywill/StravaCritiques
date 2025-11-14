from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


DEFAULT_LOGIN_URL = "http://127.0.0.1:5000/login"
DEFAULT_PROFILE_URL = "http://127.0.0.1:5000/profile"
DEFAULT_USER_DATA_DIR = Path.cwd() / ".chrome_profile"


@dataclass
class OAuthResult:
    access_token: str
    refresh_token: str
    expires_at: int
    athlete: Dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用浏览器自动化打开 Strava 登录页，并在完成授权后抓取本地 Flask 应用返回的 token。"
    )
    parser.add_argument("--login-url", default=DEFAULT_LOGIN_URL,
                        help="本地 Flask 应用的 /login 地址。")
    parser.add_argument(
        "--profile-url", default=DEFAULT_PROFILE_URL, help="登录完成后应该跳转到的 /profile 地址。")
    parser.add_argument("--headless", action="store_true",
                        help="以 headless 模式（无界面）启动浏览器。")
    parser.add_argument("--max-wait", type=int,
                        default=300, help="等待用户完成授权的最长秒数。")
    parser.add_argument(
        "--user-data-dir",
        default=str(DEFAULT_USER_DATA_DIR),
        help="指定 Chrome 用户数据目录，这样可以和现有浏览器共享 cookie/session。",
    )
    parser.add_argument(
        "--profile-directory",
        help="当用户数据目录下存在多个 profile 时，指定 profile 名称（例如 Default、Profile 1 等）。",
    )
    parser.add_argument(
        "--scope",
        default="activity:read",
        help="要请求的 Strava scope，多个 scope 用逗号隔开。",
    )
    return parser.parse_args()


def build_driver(
    headless: bool = False, user_data_dir: Path | None = None, profile_directory: str | None = None
) -> webdriver.Chrome:
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1200,900")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    if user_data_dir:
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_directory:
        chrome_options.add_argument(f"--profile-directory={profile_directory}")
    return webdriver.Chrome(options=chrome_options)


def wait_for_profile(driver: webdriver.Chrome, profile_url: str, timeout: int) -> Dict[str, Any]:
    """Wait until the OAuth flow redirects back to /profile and parse the JSON payload."""

    def on_profile_url(drv: webdriver.Chrome) -> bool:
        return drv.current_url.startswith(profile_url)

    WebDriverWait(driver, timeout).until(on_profile_url)
    try:
        pre = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "pre")))
        raw_json = pre.text
    except TimeoutException:
        raw_json = driver.page_source

    # Chrome wraps JSON in <pre>...</pre>, so strip tags if needed.
    try:
        json_start = raw_json.index("{")
        json_payload = raw_json[json_start:]
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise RuntimeError("未能在 /profile 页面中找到 JSON 数据。") from exc

    return json.loads(json_payload)


def extract_result(data: Dict[str, Any]) -> OAuthResult:
    try:
        return OAuthResult(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            athlete=data["athlete"],
        )
    except KeyError as exc:
        raise RuntimeError("返回的数据里缺少必要字段。") from exc


def dump_to_tempfile(payload: Dict[str, Any]) -> Path:
    output_dir = Path.cwd() / "user_token"
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        prefix="strava_token_",
        suffix=".json",
        dir=output_dir,
    )
    with tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
    return Path(tmp.name)


def apply_scope_to_login_url(login_url: str, scope: str) -> str:
    """Add/override the scope query parameter on the login URL."""
    parsed = urlparse(login_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["scope"] = scope
    new_query = urlencode(query)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def main() -> None:
    args = parse_args()
    login_url = apply_scope_to_login_url(args.login_url, args.scope)
    print(f"启动浏览器并打开 {login_url} ，请在弹出的窗口里完成 Strava 授权流程...")
    user_data_dir = Path(args.user_data_dir).expanduser(
    ) if args.user_data_dir else None
    if user_data_dir and not user_data_dir.exists():
        print(f"提示：用户数据目录 {user_data_dir} 不存在，将自动创建。")
        user_data_dir.mkdir(parents=True, exist_ok=True)
    driver = build_driver(args.headless, user_data_dir, args.profile_directory)
    try:
        driver.get(login_url)
        payload = wait_for_profile(driver, args.profile_url, args.max_wait)
        result = extract_result(payload)
    except TimeoutException:
        raise SystemExit("等待授权超时，请确认是否已经在浏览器中完成登录。")
    finally:
        driver.quit()

    print("\n获取成功：")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\n可用字段：")
    print(
        f"- access_token: {result.access_token[:8]}... (共 {len(result.access_token)} 字符)")
    print(
        f"- refresh_token: {result.refresh_token[:8]}... (共 {len(result.refresh_token)} 字符)")
    print(f"- expires_at: {result.expires_at}")
    print(f"- athlete id: {result.athlete.get('id')}")
    tmp_path = dump_to_tempfile(payload)
    print(f"\n已将完整 JSON 写入临时文件：{tmp_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise
