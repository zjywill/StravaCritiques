from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI


ACTIVITY_AGENT_SYSTEM_PROMPT = (
    "你是运动锐评助理。请先阅读提供的 Strava 活动 JSON，辨别运动类型，"
    "必要时调用相应工具获取指标，再给出有趣又犀利的中文点评。点评里要引用工具返回的关键数据。"
)
LATEST_ACTIVITIES_FILE = Path("latest_activities.json")
CRITIQUE_OUTPUT_FILE = Path("activity_critiques.json")
ACTIVITY_PROMPT_PATH = Path("prompts/activity_prompt.md")


def _parse_activity_payload(activity_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(activity_json)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return {"raw": activity_json}


def _format_distance(meters: Any) -> str:
    try:
        distance = float(meters)
    except (TypeError, ValueError):
        return "未知距离"
    return f"{distance / 1000:.2f} 公里"


def _format_duration(seconds: Any) -> str:
    try:
        total_seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "未知用时"
    minutes, sec = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d} 小时 {minutes:d} 分 {sec:d} 秒"
    return f"{minutes:d} 分 {sec:d} 秒"


def _format_pace(distance_m: Any, moving_time_s: Any) -> str:
    try:
        distance_km = float(distance_m) / 1000
        moving_time = float(moving_time_s)
        if distance_km <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return "配速未知"
    pace = moving_time / distance_km
    minutes, seconds = divmod(int(pace), 60)
    return f"{minutes:d}:{seconds:02d}/公里"


def _format_speed(distance_m: Any, moving_time_s: Any) -> str:
    try:
        distance_km = float(distance_m) / 1000
        moving_time = float(moving_time_s)
        if moving_time <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return "均速未知"
    speed = distance_km / (moving_time / 3600)
    return f"{speed:.1f} 公里/小时"


def _format_elevation(gain_m: Any) -> str:
    try:
        gain = float(gain_m)
    except (TypeError, ValueError):
        return "海拔增益未知"
    return f"爬升 {gain:.0f} 米"


def _format_heartrate(avg: Any, max_hr: Any) -> str:
    try:
        avg_hr = int(float(avg)) if avg is not None else None
    except (TypeError, ValueError):
        avg_hr = None
    try:
        max_val = int(float(max_hr)) if max_hr is not None else None
    except (TypeError, ValueError):
        max_val = None
    if avg_hr and max_val:
        return f"平均心率 {avg_hr}，最高 {max_val} bpm"
    if avg_hr:
        return f"平均心率 {avg_hr} bpm"
    if max_val:
        return f"最高心率 {max_val} bpm"
    return "心率未知"


def _activity_header(activity: dict[str, Any]) -> str:
    name = activity.get("name") or "未命名训练"
    sport_type = activity.get("sport_type") or activity.get("type") or "未知"
    return f"{name}｜{sport_type}"


def _log_tool_invocation(tool_name: str, activity: dict[str, Any]) -> None:
    activity_id = activity.get("id", "unknown")
    sport_type = activity.get("sport_type") or activity.get("type") or "未知类型"
    print(f"[AgentTool] {tool_name} 输入活动 {activity_id}｜{sport_type}")


@tool
def analyze_running_activity(activity_json: str) -> str:
    """根据 Strava 活动 JSON 提供跑步指标，帮助你判断配速、心率、爬升情况。"""

    activity = _parse_activity_payload(activity_json)
    _log_tool_invocation("analyze_running_activity", activity)
    distance = _format_distance(activity.get("distance"))
    moving_time = _format_duration(activity.get("moving_time"))
    pace = _format_pace(activity.get("distance"), activity.get("moving_time"))
    heartrate = _format_heartrate(
        activity.get("average_heartrate"), activity.get("max_heartrate")
    )
    elevation = _format_elevation(activity.get("total_elevation_gain"))
    cadence = activity.get("average_cadence")
    cadence_note = f"步频 {cadence:.0f}" if isinstance(
        cadence, (int, float)) else "步频未知"

    segments = [
        _activity_header(activity),
        f"距离：{distance}",
        f"移动时间：{moving_time}",
        f"平均配速：{pace}",
        f"{heartrate}",
        f"{elevation}",
        cadence_note,
    ]
    suffer_score = activity.get("suffer_score")
    if isinstance(suffer_score, (int, float)):
        segments.append(f"受虐指数 {suffer_score:.0f}")
    return "\n".join(segments)


@tool
def analyze_cycling_activity(activity_json: str) -> str:
    """根据 Strava 活动 JSON 提供骑行指标，关注速度、功率、踏频和爬升。"""

    activity = _parse_activity_payload(activity_json)
    _log_tool_invocation("analyze_cycling_activity", activity)
    distance = _format_distance(activity.get("distance"))
    moving_time = _format_duration(activity.get("moving_time"))
    elapsed_time = _format_duration(activity.get("elapsed_time"))

    # 速度显示（Strava 提供的 average_speed 单位是米/秒）
    def format_cycling_speed(avg_speed_ms: Any, max_speed_ms: Any = None) -> str:
        try:
            avg_speed = float(avg_speed_ms)
            avg_kmh = avg_speed * 3.6  # 米/秒 转 公里/小时
            result = f"平均 {avg_kmh:.1f} 公里/小时"
            if max_speed_ms is not None:
                max_speed = float(max_speed_ms)
                max_kmh = max_speed * 3.6
                result += f"，最高 {max_kmh:.1f} 公里/小时"
            return result
        except (TypeError, ValueError):
            return "速度未知"

    speed = format_cycling_speed(activity.get("average_speed"),
                                 activity.get("max_speed"))
    elevation = _format_elevation(activity.get("total_elevation_gain"))

    # 功率数据
    avg_power = activity.get("average_watts")
    device_watts = activity.get("device_watts", False)
    if isinstance(avg_power, (int, float)) and avg_power > 0:
        power_source = "功率计" if device_watts else "估算"
        power_note = f"平均功率 {avg_power:.0f} W ({power_source})"
        weighted_avg_watts = activity.get("weighted_average_watts")
        if isinstance(weighted_avg_watts, (int, float)):
            power_note += f"，加权 {weighted_avg_watts:.0f} W"
    else:
        power_note = "功率未知"

    heartrate = _format_heartrate(
        activity.get("average_heartrate"), activity.get("max_heartrate")
    )

    segments = [
        _activity_header(activity),
        f"距离：{distance}",
        f"移动时间：{moving_time}",
        f"总用时：{elapsed_time}",
        f"速度：{speed}",
        power_note,
        f"{heartrate}",
        f"{elevation}",
    ]

    # 踏频
    avg_cadence = activity.get("average_cadence")
    if isinstance(avg_cadence, (int, float)):
        segments.append(f"踏频 {avg_cadence:.0f} rpm")

    # 温度
    avg_temp = activity.get("average_temp")
    if isinstance(avg_temp, (int, float)):
        segments.append(f"温度 {avg_temp:.0f}°C")

    # 卡路里
    if isinstance(activity.get("calories"), (int, float)):
        segments.append(f"卡路里 {activity['calories']:.0f}")

    # 训练环境
    if activity.get("trainer"):
        segments.append("环境：训练台")
    else:
        segments.append("环境：户外骑行")

    return "\n".join(segments)


@tool
def analyze_swimming_activity(activity_json: str) -> str:
    """根据 Strava 活动 JSON 提供游泳指标，关注配速、速度和心率。"""

    activity = _parse_activity_payload(activity_json)
    _log_tool_invocation("analyze_swimming_activity", activity)
    distance = _format_distance(activity.get("distance"))
    moving_time = _format_duration(activity.get("moving_time"))
    elapsed_time = _format_duration(activity.get("elapsed_time"))

    # 游泳配速通常以每100米为单位
    def format_swim_pace(distance_m: Any, moving_time_s: Any) -> str:
        try:
            distance = float(distance_m)
            time_seconds = float(moving_time_s)
            if distance <= 0:
                raise ValueError
            pace_per_100m = (time_seconds / distance) * 100
            minutes, seconds = divmod(int(pace_per_100m), 60)
            return f"{minutes:d}:{seconds:02d}/100米"
        except (TypeError, ValueError):
            return "配速未知"

    # 格式化速度（Strava游泳数据中 average_speed 单位是米/秒）
    def format_swim_speed(speed_ms: Any, max_speed_ms: Any = None) -> str:
        try:
            speed = float(speed_ms)
            speed_kmh = speed * 3.6  # 米/秒 转 公里/小时
            result = f"平均 {speed_kmh:.2f} 公里/小时"
            if max_speed_ms is not None:
                max_speed = float(max_speed_ms)
                max_kmh = max_speed * 3.6
                result += f"，最高 {max_kmh:.2f} 公里/小时"
            return result
        except (TypeError, ValueError):
            return "速度未知"

    pace = format_swim_pace(activity.get("distance"),
                            activity.get("moving_time"))
    speed = format_swim_speed(activity.get("average_speed"),
                              activity.get("max_speed"))
    heartrate = _format_heartrate(
        activity.get("average_heartrate"), activity.get("max_heartrate")
    )

    segments = [
        _activity_header(activity),
        f"距离：{distance}",
        f"移动时间：{moving_time}",
        f"总用时：{elapsed_time}",
        f"平均配速：{pace}",
        f"速度：{speed}",
        f"{heartrate}",
    ]

    # 划水频率 (strokes per minute) - 有些设备可能没有这个数据
    avg_cadence = activity.get("average_cadence")
    if isinstance(avg_cadence, (int, float)):
        segments.append(f"划水频率 {avg_cadence:.0f} spm")

    # 卡路里 - 有些活动可能没有这个数据
    if isinstance(activity.get("calories"), (int, float)):
        segments.append(f"卡路里 {activity['calories']:.0f}")

    # 训练环境标识
    if activity.get("trainer"):
        segments.append("环境：泳池训练")

    return "\n".join(segments)


@tool
def inspect_general_activity(activity_json: str) -> str:
    """当运动类型未知或为通用健身追踪时，给出全面的指标摘要。"""

    activity = _parse_activity_payload(activity_json)
    _log_tool_invocation("inspect_general_activity", activity)

    # 基础信息
    distance = activity.get("distance")
    distance_note = _format_distance(
        distance) if distance is not None else "无距离记录"
    moving_time = _format_duration(activity.get("moving_time"))
    elapsed_time = _format_duration(activity.get("elapsed_time"))

    notes = [
        _activity_header(activity),
        f"距离：{distance_note}",
        f"移动时间：{moving_time}",
        f"总用时：{elapsed_time}",
    ]

    # 速度信息（如果有距离和时间数据）
    avg_speed = activity.get("average_speed")
    max_speed = activity.get("max_speed")
    if isinstance(avg_speed, (int, float)) and avg_speed > 0:
        speed_kmh = avg_speed * 3.6
        speed_text = f"平均速度：{speed_kmh:.1f} 公里/小时"
        if isinstance(max_speed, (int, float)):
            max_kmh = max_speed * 3.6
            speed_text += f"，最高 {max_kmh:.1f} 公里/小时"
        notes.append(speed_text)

    # 心率
    if activity.get("average_heartrate") or activity.get("max_heartrate"):
        notes.append(
            _format_heartrate(
                activity.get("average_heartrate"),
                activity.get("max_heartrate")
            )
        )

    # 海拔增益
    if isinstance(activity.get("total_elevation_gain"), (int, float)):
        notes.append(_format_elevation(activity.get("total_elevation_gain")))

    # 踏频/步频（某些活动可能有）
    avg_cadence = activity.get("average_cadence")
    if isinstance(avg_cadence, (int, float)):
        notes.append(f"步频/踏频 {avg_cadence:.0f}")

    # 温度
    avg_temp = activity.get("average_temp")
    if isinstance(avg_temp, (int, float)):
        notes.append(f"温度 {avg_temp:.0f}°C")

    # 卡路里
    if isinstance(activity.get("calories"), (int, float)):
        notes.append(f"卡路里 {activity['calories']:.0f}")

    # 训练环境
    if activity.get("trainer"):
        notes.append("环境：室内训练")
    elif activity.get("start_latlng"):
        notes.append("环境：户外活动")

    return "\n".join(notes)


def build_activity_agent(
    system_prompt: str = ACTIVITY_AGENT_SYSTEM_PROMPT,
    *,
    model: str = "gpt-3.5-turbo",
    base_url: str | None = None,
    api_key: str | None = None,
):
    """Create the latest LangChain agent for activity analysis."""

    llm = ChatOpenAI(model=model, base_url=base_url, api_key=api_key)
    tools = [
        analyze_running_activity,
        analyze_cycling_activity,
        analyze_swimming_activity,
        inspect_general_activity,
    ]
    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


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


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                text = chunk.get("text")
                if text:
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return ""


def _extract_agent_output(agent_payload: Any) -> str | None:
    if isinstance(agent_payload, dict):
        messages = agent_payload.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, BaseMessage):
                    text = _stringify_message_content(message.content)
                    if text:
                        return text.strip()
        structured = agent_payload.get("structured_response")
        if isinstance(structured, str):
            return structured.strip()
    return None


def generate_agent_critique(agent: Any, activity: dict[str, Any]) -> str:
    """Invoke the configured agent to produce a critique for an activity."""

    agent_prompt = build_activity_prompt(activity)
    agent_response = agent.invoke({
        "messages": [HumanMessage(content=agent_prompt)],
    })
    critique = _extract_agent_output(agent_response)
    if not isinstance(critique, str) or not critique.strip():
        raise RuntimeError("Agent failed to return critique text for activity")
    return critique.strip()


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
    resolved_api_key = os.getenv("ONE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Create a .env file or export the variable.")

    resolved_model = (
        os.getenv("ONE_API_MODEL")
        or os.getenv("OPENAI_API_MODEL")
        or "gpt-3.5-turbo"
    )
    resolved_base_url = os.getenv(
        "ONE_API_REMOTE") or os.getenv("OPENAI_BASE_URL")
    resolved_agent_prompt = (
        os.getenv("LLM_ACTIVITY_AGENT_PROMPT")
        or os.getenv(
            "LLM_SYSTEM_PROMPT",
            ACTIVITY_AGENT_SYSTEM_PROMPT,
        )
    )

    activities = load_activities()
    if not activities:
        raise RuntimeError(f"No activities found in {LATEST_ACTIVITIES_FILE}.")

    print(f"Loaded {resolved_api_key}")
    agent = build_activity_agent(
        system_prompt=resolved_agent_prompt,
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
        critique = generate_agent_critique(agent, activity)
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
