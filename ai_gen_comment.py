from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


DEFAULT_SYSTEM_PROMPT = "You are a concise assistant."
LATEST_ACTIVITIES_FILE = Path("latest_activities.json")
CRITIQUE_OUTPUT_FILE = Path("activity_critiques.json")
ACTIVITY_PROMPT_PATH = Path("prompts/activity_prompt.md")


def build_chain(
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    *,
    model: str = "gpt-3.5-turbo",
    base_url: str | None = None,
    api_key: str | None = None,
):
    """Wire together the LangChain runnable graph for the configured backend."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{question}"),
        ]
    )
    print(
        f"Using model: {model} at {base_url or 'default endpoint'} api_key={'set' if api_key else 'not set'}")
    llm = ChatOpenAI(model=model, base_url=base_url, api_key=api_key)
    parser = StrOutputParser()
    return prompt | llm | parser


def load_activities(path: Path = LATEST_ACTIVITIES_FILE) -> list[dict[str, Any]]:
    """Load Strava activities from disk, ensuring we have a list structure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing activities file: {path}") from exc
    if not isinstance(data, list):
        raise RuntimeError(
            "latest_activities.json must contain a list of activities.")
    return [activity for activity in data if isinstance(activity, dict)]


def _load_activity_instruction() -> str:
    """Load the critique prompt template from the markdown file."""
    try:
        content = ACTIVITY_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Missing activity prompt template: {ACTIVITY_PROMPT_PATH}"
        ) from exc
    if not content:
        raise RuntimeError(
            f"Activity prompt template {ACTIVITY_PROMPT_PATH} is empty."
        )
    return content


def build_activity_prompt(activity: dict[str, Any]) -> str:
    """Create a sarcastic Chinese critique prompt for the provided activity."""
    instruction = _load_activity_instruction()

    details = json.dumps(
        activity,
        ensure_ascii=False,
        indent=2,
    )

    return f"{instruction}\n\n活动 JSON:\n{details}"


def load_existing_critiques(
    path: Path = CRITIQUE_OUTPUT_FILE,
) -> dict[str, dict[str, Any]]:
    """Load stored critiques, normalizing legacy string-only entries."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid critiques file: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"{path} must contain an object keyed by activity id.")

    normalized: dict[str, dict[str, Any]] = {}
    for activity_id, entry in data.items():
        if isinstance(entry, dict):
            critique_text = entry.get("critique")
            uploaded = bool(entry.get("uploaded", False))
            if isinstance(critique_text, str):
                normalized[activity_id] = {
                    "critique": critique_text,
                    "uploaded": uploaded,
                }
        elif isinstance(entry, str):
            normalized[activity_id] = {"critique": entry, "uploaded": False}
    return normalized


def generate_critiques() -> None:
    """Read local activities, ask the LLM to critique each, and persist the results."""
    load_dotenv()
    resolved_api_key = os.getenv("ONE_API_KEY")
    if not resolved_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Create a .env file or export the variable.")

    resolved_model = os.getenv(
        "ONE_API_MODEL") or "gpt-3.5-turbo"
    resolved_base_url = os.getenv("ONE_API_REMOTE")
    resolved_system_prompt = os.getenv(
        "LLM_SYSTEM_PROMPT",
        "You are a concise assistant that writes witty Chinese critiques about workouts.",
    )

    activities = load_activities()
    if not activities:
        raise RuntimeError(f"No activities found in {LATEST_ACTIVITIES_FILE}.")

    print(f"Loaded {resolved_api_key}")
    chain = build_chain(
        system_prompt=resolved_system_prompt,
        model=resolved_model,
        base_url=resolved_base_url,
        api_key=resolved_api_key,
    )

    total = len(activities)
    critiques = load_existing_critiques()
    for index, activity in enumerate(activities, start=1):
        activity_id = str(activity.get("id", "unknown"))
        existing_entry = critiques.get(activity_id)
        if existing_entry and existing_entry.get("uploaded"):
            print(f"[{index}/{total}] 活动 {activity_id} 已上传，跳过生成。")
            continue

        print(f"[{index}/{total}] 开始生成活动 {activity_id} 的锐评...")
        prompt = build_activity_prompt(activity)
        critique = chain.invoke({"question": prompt}).strip()
        critiques[activity_id] = {
            "critique": critique,
            "uploaded": False,
        }
        print(f"[{index}/{total}] 活动 {activity_id} 生成完毕。")

    CRITIQUE_OUTPUT_FILE.write_text(
        json.dumps(critiques, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已生成 {len(critiques)} 条锐评，保存在 {CRITIQUE_OUTPUT_FILE}.")


def main() -> None:
    generate_critiques()


if __name__ == "__main__":
    main()
