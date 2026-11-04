"""规范化哈希（ADR-0011）。

`market_data_hash` 必须可复现：同一组输入在回放与实时得到同一哈希，因此
- key 排序固定；
- Decimal / datetime 先转成稳定字符串；
- 记录集合的顺序不影响结果（顺序无关），这样"同一快照、不同抓取顺序"不会被误判为数据漂移。
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from bfgi.core.errors import BfgiError, ErrorCode
from bfgi.core.timeutil import format_utc


def canonical_json(value: Any) -> str:
    """确定性 JSON：排序 key、非 ASCII 不转义、Decimal/datetime 归一为字符串。"""
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return format_utc(value)
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        # 集合顺序不稳定：排序其规范化形式，保证确定性。
        return sorted(canonical_json(v) for v in value)
    if isinstance(value, bool) or isinstance(value, (str, int)) or value is None:
        return value
    if isinstance(value, float):
        # docs/02 §7：float 不应进入权威数据路径；哈希层直接拒绝，避免隐式精度差异。
        raise BfgiError(ErrorCode.INVALID_DECIMAL, "哈希输入不接受 float：请先转成 Decimal 或字符串", {"type": "float"})
    raise BfgiError(ErrorCode.INVALID_VALUE, f"哈希输入类型不受支持：{type(value).__name__}")


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_hash(record: Any) -> str:
    """单条记录（或任意值）的哈希。"""
    return sha256_hex(canonical_json(record))


def market_data_hash(records: Iterable[Any]) -> str:
    """关键输入集合的哈希（顺序无关）。空集合也给出稳定哈希，便于区分"无输入"与"未计算"。"""
    digests = sorted(record_hash(r) for r in records)
    return sha256_hex("".join(digests))


def fixture_set_hash(fixture_ids: Iterable[str]) -> str:
    """fixture 集哈希（ADR-0011：fixture 场景用 fixture 集哈希作为 market_data_hash）。"""
    ids = sorted({str(i) for i in fixture_ids if str(i)})
    if not ids:
        raise BfgiError(ErrorCode.INVALID_VALUE, "fixture 集不能为空")
    return sha256_hex("\n".join(ids))
