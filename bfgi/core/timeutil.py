"""UTC 时间工具（SYS-004）。

AGENTS.md §7：所有时间 UTC；回放与实时产生相同输出。因此本模块不接受 naive datetime，
也不做本地时区推断——需要本地展示是 Web 层职责（docs/07）。
"""

from datetime import UTC, datetime, timedelta

from bfgi.core.constants import MAX_PLAN_VALID_MINUTES
from bfgi.core.errors import BfgiError, ErrorCode


def utc_now() -> datetime:
    """当前 UTC 时间（带 tzinfo）。可被调用方注入替代以做确定性回放。"""
    return datetime.now(UTC)


def parse_utc(value: str | datetime) -> datetime:
    """把 ISO-8601 字符串或 datetime 规范化为 UTC aware datetime。

    - 字符串必须以 `Z` 或显式偏移结尾；naive 字符串拒绝（避免"哪个时区"的静默错误）。
    - naive datetime 拒绝；aware datetime 转换到 UTC。
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise BfgiError(
                ErrorCode.INVALID_TIME,
                "naive datetime 被拒绝：所有时间必须带 UTC/偏移信息",
                {"value": value.isoformat()},
            )
        return value.astimezone(UTC)

    if not isinstance(value, str):
        raise BfgiError(ErrorCode.INVALID_TIME, "时间必须是 ISO-8601 字符串或 datetime", {"type": type(value).__name__})

    text = value.strip()
    if not text:
        raise BfgiError(ErrorCode.INVALID_TIME, "时间字符串为空")
    # datetime.fromisoformat 在 3.12 支持 'Z'；仍统一走同一入口，避免各处自行解析。
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise BfgiError(ErrorCode.INVALID_TIME, f"无法解析时间：{text!r}") from exc
    return parse_utc(parsed)


def format_utc(value: datetime) -> str:
    """序列化为 `...Z`（docs/07：时间 ISO-8601 UTC）。"""
    dt = parse_utc(value)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def floor_to_slot(value: datetime, interval_minutes: int) -> datetime:
    """把时间对齐到 interval 的 slot 起点（ADR-0003 的 `slot_at` 语义）。

    用于调度幂等：同一 slot 的重复触发只执行一次。
    """
    if interval_minutes <= 0:
        raise BfgiError(ErrorCode.INVALID_VALUE, "interval_minutes 必须为正整数", {"interval_minutes": interval_minutes})
    dt = parse_utc(value)
    minutes_of_day = dt.hour * 60 + dt.minute
    floored = (minutes_of_day // interval_minutes) * interval_minutes
    return (dt - timedelta(minutes=minutes_of_day - floored)).replace(second=0, microsecond=0)


def minutes_between(start: datetime, end: datetime) -> int:
    """end - start 的整分钟数（向下取整）。允许负值表示倒序。"""
    a = parse_utc(start)
    b = parse_utc(end)
    return int((b - a).total_seconds() // 60)


def is_within_plan_validity(as_of_utc: datetime, valid_until_utc: datetime, max_minutes: int = MAX_PLAN_VALID_MINUTES) -> bool:
    """docs/04：`valid_until <= as_of + 4h` 且必须严格晚于 as_of。"""
    if max_minutes <= 0:
        raise BfgiError(ErrorCode.INVALID_VALUE, "max_minutes 必须为正整数", {"max_minutes": max_minutes})
    delta = minutes_between(as_of_utc, valid_until_utc)
    return 0 < delta <= max_minutes
