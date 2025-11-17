from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from post_comment import (
    ensure_access_token,
    load_critiques,
    pending_items,
    save_critiques,
    update_activity_description,
)
from latest_activity import fetch_latest_activity
from ai_gen_comment import (
    ACTIVITY_AGENT_SYSTEM_PROMPT,
    CRITIQUE_OUTPUT_FILE,
    LATEST_ACTIVITIES_FILE,
    build_activity_agent,
    generate_agent_critique,
    load_activities,
    load_existing_critiques,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "抓取最新 Strava 活动，生成毒舌点评，并可选择自动回写 description。"
        )
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=1,
        help="调用活动 API 时请求的条数（默认：1）。",
    )
    parser.add_argument(
        "--activities-file",
        type=Path,
        default=LATEST_ACTIVITIES_FILE,
        help="活动 JSON 的存储路径（默认：latest_activities.json）。",
    )
    parser.add_argument(
        "--critiques-file",
        type=Path,
        default=CRITIQUE_OUTPUT_FILE,
        help="点评 JSON 的存储路径（默认：activity_critiques.json）。",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        help="可选：指定 user_token 目录下的 token JSON。",
    )
    parser.add_argument(
        "--model",
        help="覆盖 LLM 模型名称（默认读取 ONE_API_MODEL 或 gpt-3.5-turbo）。",
    )
    parser.add_argument(
        "--base-url",
        help="覆盖 LLM 接口地址（默认读取 ONE_API_REMOTE）。",
    )
    parser.add_argument(
        "--api-key",
        help="覆盖 LLM API Key（默认读取 ONE_API_KEY 或 OPENAI_API_KEY）。",
    )
    parser.add_argument(
        "--system-prompt",
        help="覆盖系统提示词（默认读取 LLM_SYSTEM_PROMPT）。",
    )
    parser.add_argument(
        "--max-upload",
        type=int,
        help="本次最多上传多少条点评，默认不限制。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅展示将要写入的描述，不真正调用写接口。",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="跳过抓取活动，直接使用 activities-file 中已有的数据。",
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="跳过生成点评，只执行上传阶段。",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="跳过上传描述，只抓取并生成点评。",
    )
    parser.add_argument(
        "--regenerate-uploaded",
        action="store_true",
        help="强制重新生成并上传已标记为 uploaded 的点评。",
    )
    return parser.parse_args()


def _resolve_llm_config(args: argparse.Namespace) -> dict[str, Any]:
    api_key = args.api_key or os.getenv("ONE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 LLM API Key，请设置 ONE_API_KEY/OPENAI_API_KEY 或使用 --api-key。")

    agent_prompt = (
        args.system_prompt
        or os.getenv("LLM_ACTIVITY_AGENT_PROMPT")
        or os.getenv("LLM_SYSTEM_PROMPT")
        or ACTIVITY_AGENT_SYSTEM_PROMPT
    )
    config = {
        "agent_prompt": agent_prompt,
        "model": args.model or os.getenv("ONE_API_MODEL", "gpt-3.5-turbo"),
        "base_url": args.base_url or os.getenv("ONE_API_REMOTE"),
        "api_key": api_key,
    }
    return config


def fetch_activities(
    access_token: str,
    *,
    per_page: int,
    output: Path,
) -> list[dict[str, Any]]:
    activities = fetch_latest_activity(access_token, per_page)
    output.write_text(
        json.dumps(activities, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已抓取 {len(activities)} 条活动，写入 {output}。")
    return [item for item in activities if isinstance(item, dict)]


def generate_critiques_for(
    activities: list[dict[str, Any]],
    *,
    critiques_path: Path,
    agent_prompt: str,
    model: str,
    base_url: str | None,
    api_key: str,
    regenerate_uploaded: bool = False,
) -> dict[str, dict[str, Any]]:
    if not activities:
        raise RuntimeError("活动列表为空，无法生成点评。")

    agent = build_activity_agent(
        system_prompt=agent_prompt,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )
    critiques = load_existing_critiques(critiques_path)
    total = len(activities)
    for idx, activity in enumerate(activities, start=1):
        activity_id = str(activity.get("id", "unknown"))
        record = critiques.get(activity_id)
        if record and record.get("uploaded"):
            if not regenerate_uploaded:
                print(f"[{idx}/{total}] 活动 {activity_id} 已上传点评，跳过生成。")
                continue
            print(
                f"[{idx}/{total}] 活动 {activity_id} 已上传点评，因 --regenerate-uploaded 重新生成。"
            )

        print(f"[{idx}/{total}] 正在生成活动 {activity_id} 的点评...")
        critique = generate_agent_critique(agent, activity)
        critiques[activity_id] = {"critique": critique, "uploaded": False}
        print(f"[{idx}/{total}] 已生成活动 {activity_id} 的点评。")

    critiques_path.write_text(
        json.dumps(critiques, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"点评已保存至 {critiques_path}。")
    return critiques


def upload_pending_critiques(
    critiques: dict[str, dict[str, Any]],
    *,
    path: Path,
    access_token: str,
    max_count: int | None,
    dry_run: bool,
) -> int:
    todo = list(pending_items(critiques))
    if not todo:
        print("没有需要上传的点评。")
        return 0

    if max_count is not None:
        todo = todo[:max_count]

    processed = 0
    for activity_id, detail in todo:
        critique = detail.get("critique")
        if not isinstance(critique, str) or not critique.strip():
            print(f"[跳过] 活动 {activity_id} 缺少有效的 critique 字段。")
            continue

        if dry_run:
            preview = critique.replace("\n", " ")[:60]
            print(f"[预览] 将把活动 {activity_id} 的描述更新为：{preview}...")
            continue

        try:
            result = update_activity_description(access_token, activity_id, critique)
        except Exception as exc:  # pragma: no cover - HTTP 失败时触发
            print(f"[失败] 无法更新活动 {activity_id}：{exc}")
            continue

        detail["uploaded"] = True
        detail["updated_description"] = result.get("description", critique)
        detail["uploaded_at"] = datetime.now(tz=timezone.utc).isoformat()
        save_critiques(path, critiques)
        processed += 1
        print(f"[成功] 已更新活动 {activity_id} 的描述。")

    if dry_run:
        print("Dry run 完成，仅展示了准备更新的描述。")
    else:
        print(f"上传完成，共更新 {processed} 条活动描述。")
    return processed


def main() -> None:
    load_dotenv()
    args = parse_args()

    need_token = not args.skip_fetch or not args.skip_upload
    access_token = None
    token_path: Path | None = None
    if need_token:
        access_token, token_path = ensure_access_token(args.token_file)
        print(f"使用 token 文件：{token_path}")

    activities: list[dict[str, Any]] = []
    if args.skip_fetch:
        activities = load_activities(args.activities_file)
        print(
            f"跳过抓取，使用 {args.activities_file} 中的 {len(activities)} 条活动。"
        )
    else:
        if access_token is None:
            raise RuntimeError("无法抓取活动：缺少 access token。")
        activities = fetch_activities(
            access_token,
            per_page=args.per_page,
            output=args.activities_file,
        )

    critiques: dict[str, dict[str, Any]]
    if args.skip_generate:
        critiques = load_critiques(args.critiques_file)
        print(
            f"跳过生成，直接从 {args.critiques_file} 读取 {len(critiques)} 条点评。"
        )
    else:
        llm_config = _resolve_llm_config(args)
        critiques = generate_critiques_for(
            activities,
            critiques_path=args.critiques_file,
            regenerate_uploaded=args.regenerate_uploaded,
            **llm_config,
        )

    if args.skip_upload:
        print("跳过上传，流程结束。")
        return

    if access_token is None:
        access_token, token_path = ensure_access_token(args.token_file)
        print(f"使用 token 文件：{token_path}")

    upload_pending_critiques(
        critiques,
        path=args.critiques_file,
        access_token=access_token,
        max_count=args.max_upload,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
