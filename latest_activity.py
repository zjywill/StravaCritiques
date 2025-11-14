from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 user_token 目录中的 JSON，并获取最新一条 Strava Activity。"
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        help="指定 token JSON 文件路径（默认使用 user_token 目录下最新的一个文件）。",
    )
    parser.add_argument("--per-page", type=int, default=1, help="要请求的活动数量，默认为 1。")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("latest_activities.json"),
        help="将获取到的活动写入的文件路径，默认为 ./latest_activities.json。",
    )
    return parser.parse_args()


def find_latest_token_file() -> Path:
    token_dir = Path("user_token")
    if not token_dir.exists():
        raise FileNotFoundError("user_token 目录不存在，请先运行授权脚本。")
    candidates = sorted(token_dir.glob("strava_token_*.json"))
    if not candidates:
        raise FileNotFoundError("user_token 目录中未找到任何 token JSON 文件。")
    return candidates[-1]


def load_token(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_token(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def needs_refresh(token_payload: Dict[str, Any]) -> bool:
    expires_at = int(token_payload.get("expires_at", 0))
    return expires_at <= int(time.time()) + 60


def refresh_token(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("缺少 STRAVA_CLIENT_ID 或 STRAVA_CLIENT_SECRET，请在 .env 中配置。")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": payload.get("refresh_token"),
    }
    response = requests.post(TOKEN_URL, data=data, timeout=10)
    response.raise_for_status()
    new_payload = response.json()
    save_token(path, new_payload)
    return new_payload


def fetch_latest_activity(access_token: str, per_page: int) -> Any:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": per_page}
    response = requests.get(ACTIVITIES_URL, headers=headers, params=params, timeout=10)
    if response.status_code in {401, 403}:
        detail = response.json().get("message", "未授权")
        raise RuntimeError(f"请求被拒绝：{detail}。请确认授权时包含 activity:read scope。")
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()
    args = parse_args()
    token_path = args.token_file or find_latest_token_file()
    token_payload = load_token(token_path)
    if needs_refresh(token_payload):
        print("access token 已过期，尝试使用 refresh_token 更新...")
        token_payload = refresh_token(token_path, token_payload)
        print("已成功刷新 token。")

    try:
        activities = fetch_latest_activity(token_payload["access_token"], args.per_page)
    except RuntimeError as err:
        raise SystemExit(f"获取活动失败：{err}")

    args.output.write_text(json.dumps(activities, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"已将活动写入 {args.output}")


if __name__ == "__main__":
    main()
