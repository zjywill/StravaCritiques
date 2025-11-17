from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import requests
from dotenv import load_dotenv

from latest_activity import (
    find_latest_token_file,
    load_token,
    needs_refresh,
    refresh_token,
)

UPDATE_URL_TEMPLATE = "https://www.strava.com/api/v3/activities/{activity_id}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="读取 JSON 文件中的毒舌点评，并将其同步为目标活动的 description。"
    )
    parser.add_argument(
        "--critiques-file",
        type=Path,
        default=Path("activity_critiques.json"),
        help="包含活动点评的 JSON 文件路径（默认：activity_critiques.json）。",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        help="指定 user_token 目录中的 token JSON（默认选择最新文件）。",
    )
    parser.add_argument(
        "--max-count",
        type=int,
        help="本次最多更新描述的活动数量，用于防止一次性批量操作。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要更新的活动及描述，不真正调用 Strava API。",
    )
    return parser.parse_args()


def load_critiques(path: Path) -> Dict[str, Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_critiques(path: Path, payload: Dict[str, Dict[str, Any]]) -> None:
    path.write_text(json.dumps(payload, indent=2,
                    ensure_ascii=False), encoding="utf-8")


def pending_items(data: Dict[str, Dict[str, Any]]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    for activity_id, detail in data.items():
        if not detail.get("uploaded"):
            yield activity_id, detail


def ensure_access_token(token_file: Path | None) -> Tuple[str, Path]:
    token_path = token_file or find_latest_token_file()
    payload = load_token(token_path)
    if needs_refresh(payload):
        print("access token 将过期，尝试刷新...")
        payload = refresh_token(token_path, payload)
        print("已刷新 access token。")
    return payload["access_token"], token_path


def _format_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "<empty body>"
    message = payload.get("message")
    errors = payload.get("errors")
    if errors:
        return f"{message} | errors={errors}"
    return str(message or payload)


def update_activity_description(access_token: str, activity_id: str, text: str) -> Dict[str, Any]:
    url = UPDATE_URL_TEMPLATE.format(activity_id=activity_id)
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.put(url, headers=headers, data={"description": text}, timeout=10)
    if response.status_code in {401, 403}:
        raise RuntimeError("更新活动描述被拒绝，确认 token 是否包含 activity:write scope。")
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = _format_error_detail(response)
        raise RuntimeError(
            f"Strava API 错误（status={response.status_code}）：{detail}"
        ) from exc
    return response.json()


def main() -> None:
    load_dotenv()
    args = parse_args()
    critiques_path = args.critiques_file
    if not critiques_path.exists():
        raise SystemExit(f"未找到点评文件：{critiques_path}")
    critiques = load_critiques(critiques_path)
    todo = list(pending_items(critiques))
    if not todo:
        print("没有需要上传的点评，所有条目都已标记为 uploaded=true。")
        return

    if args.max_count is not None:
        todo = todo[: args.max_count]
    access_token, token_path = ensure_access_token(args.token_file)
    print(f"使用 token 文件：{token_path}")

    processed = 0
    for activity_id, detail in todo:
        critique = detail.get("critique")
        if not isinstance(critique, str) or not critique.strip():
            print(f"[跳过] 活动 {activity_id} 缺少有效的 critique 字段。")
            continue

        if args.dry_run:
            print(f"[预览] 将把活动 {activity_id} 的描述更新为：{critique[:60]}...")
            continue

        try:
            result = update_activity_description(
                access_token, activity_id, critique)
        except Exception as exc:  # pragma: no cover - network failure path
            print(f"[失败] 无法更新活动 {activity_id} 的描述：{exc}")
            continue

        detail["uploaded"] = True
        detail["updated_description"] = result.get("description", critique)
        detail["uploaded_at"] = datetime.now(tz=timezone.utc).isoformat()
        save_critiques(critiques_path, critiques)
        processed += 1
        print(f"[成功] 已更新活动 {activity_id} 的描述。")

    if args.dry_run:
        print("Dry run 完成，仅展示了准备更新的描述。")
    else:
        print(f"完成，本次共成功更新 {processed} 条活动描述。")


if __name__ == "__main__":
    main()
