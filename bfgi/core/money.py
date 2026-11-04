"""价格/数量的 Decimal 规则（SYS-004）。

docs/02 §7：价格必须 Decimal 或以字符串序列化，**float 只能作为中间计算值，不能决定 tick/数量合规**。
因此本模块默认拒绝 float 进入价格路径；确实需要从 float 转换（中间值）时必须显式调用
`decimal_from_float`，并保证定标（places）——这是留痕的逃生通道，不是默认行为。
"""

from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)
from enum import StrEnum
from typing import Any

from bfgi.core.errors import BfgiError, ErrorCode

Price = Decimal
Ratio = Decimal


class TickRounding(StrEnum):
    """tick 量化方向。调用方必须显式选择，不隐藏舍入策略（入场与止损的保守方向不对称）。"""

    HALF_UP = "HALF_UP"
    CEILING = "CEILING"
    FLOOR = "FLOOR"


# `decimal.ROUND_*` 的具体类型在不同 Python 实现（_pydecimal vs _decimal）下不一致；
# 领域层只暴露自己的枚举，映射集中在这里，避免类型与行为随实现漂移。
_ROUNDING_TABLE: dict[TickRounding, Any] = {
    TickRounding.HALF_UP: ROUND_HALF_UP,
    TickRounding.CEILING: ROUND_CEILING,
    TickRounding.FLOOR: ROUND_FLOOR,
}

# 防御性上限：限制**有效位数**（不是量级）。`1E50` 只有 1 位有效数字，属于合法的科学计数法输入；
# 但 `1234567890123456789012345678901.1` 这类明显不是交易所 tick 的脏数据要在这里挡住。
# 价格量级本身的合理性属于 market_data 层（docs/03 的 mark price 校验），不在这里猜。
_MAX_DECIMAL_DIGITS = 30


def to_decimal(value: object, field: str) -> Decimal:
    """把输入转成 Decimal，**拒绝 bool / float / 非有限值 / 非法字符串**。

    拒绝 bool 是因为 `True` 会被静默当成 1；拒绝 float 是为了守住 docs/02 §7 的边界。
    """
    if isinstance(value, bool):
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 不接受布尔值", {"field": field, "value": value})
    if isinstance(value, float):
        raise BfgiError(
            ErrorCode.INVALID_DECIMAL,
            f"字段 {field} 不接受 float：请用字符串或 Decimal（float 只能是中间值，见 docs/02 §7）",
            {"field": field, "value": repr(value)},
        )
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 为空字符串", {"field": field})
        try:
            result = Decimal(text)
        except InvalidOperation as exc:
            raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 不是合法数字：{text!r}", {"field": field}) from exc
    else:
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 类型不受支持：{type(value).__name__}", {"field": field})

    if not result.is_finite():
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 必须有限（拒绝 NaN/Inf）", {"field": field, "value": str(result)})
    if len(result.as_tuple().digits) > _MAX_DECIMAL_DIGITS:
        raise BfgiError(
            ErrorCode.INVALID_DECIMAL,
            f"字段 {field} 有效位数超出可处理范围",
            {"field": field, "digits": len(result.as_tuple().digits)},
        )
    return result


def decimal_from_float(value: float, places: int, field: str) -> Decimal:
    """中间计算值 → Decimal 的显式逃生通道（定标到 `places` 位）。

    只用于统计类中间量（例如均值）转成可序列化 Decimal；不得用于 tick/最小数量/名义价值合规判断。
    """
    if isinstance(value, bool) or not isinstance(value, float):
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"decimal_from_float 只接受 float：{field}", {"field": field})
    if places < 0:
        raise BfgiError(ErrorCode.INVALID_VALUE, "places 必须 >= 0", {"field": field, "places": places})
    d = to_decimal(repr(value), field)
    return d.quantize(Decimal(1).scaleb(-places))


def to_price_str(value: Decimal) -> str:
    """Decimal → 稳定字符串（不使用科学计数法，保留原有小数位）。docs/07：价格用 Decimal 字符串。"""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise BfgiError(ErrorCode.INVALID_DECIMAL, "价格必须是有限 Decimal")
    return format(value, "f")


def _require_finite_decimal(value: Decimal, field: str) -> Decimal:
    """有限性守卫（SYS-004 复测发现的根因）。

    `Decimal("NaN") <= 0` 为 False，因此旧实现把 NaN/Inf 当成合法正数放行；随后 `divmod(NaN, tick)`
    或 `NaN.quantize(...)` 会抛出底层 `decimal.InvalidOperation`——原始 decimal 异常外泄等于把脏数据
    透传给调用方。必须在入口 fail-closed，而不是在调用处特判。
    """
    if not isinstance(value, Decimal):
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 必须是 Decimal", {"field": field})
    if not value.is_finite():
        raise BfgiError(ErrorCode.INVALID_DECIMAL, f"字段 {field} 必须是有限 Decimal（拒绝 NaN/Inf）", {"field": field})
    return value


def validate_positive(value: Decimal, field: str) -> Decimal:
    _require_finite_decimal(value, field)
    if value <= 0:
        raise BfgiError(ErrorCode.INVALID_VALUE, f"字段 {field} 必须为正", {"field": field, "value": to_price_str(value)})
    return value


def is_multiple_of_tick(value: Decimal, tick: Decimal) -> bool:
    """value 是否精确落在 tick 的整数倍上（不近似）。"""
    validate_positive(tick, "tickSize")
    _require_finite_decimal(value, "value")
    if value < 0:
        return False
    quotient, remainder = divmod(value, tick)
    return remainder == 0 and quotient.is_finite()


def quantize_to_tick(price: Decimal, tick: Decimal, rounding: TickRounding = TickRounding.HALF_UP) -> Decimal:
    """把价格对齐到交易所 tickSize（docs/05：始终使用实时 exchange filters）。

    - tick 必须 > 0；
    - price 必须 >= 0：价格来自交易所盘口，恒为正（docs/03）。`is_multiple_of_tick` 对负数恒返回
      False，若不在这里挡住，负价格会落到"tickSize 可能不是 10 的负幂"这条误导消息上（SYS-004 复测发现）；
    - `rounding` 显式给出（默认 HALF_UP），保守方向由调用方选择（CEILING/FLOOR）；
    - 返回结果保证是 tick 的整数倍，否则说明 tick 本身不是 10 的负幂（异常盘口/脏数据）。
    """
    validate_positive(tick, "tickSize")
    _require_finite_decimal(price, "price")
    if price < 0:
        raise BfgiError(
            ErrorCode.INVALID_VALUE,
            "字段 price 不能为负：tick 量化只用于交易所盘口价格",
            {"field": "price", "value": to_price_str(price)},
        )
    if rounding not in _ROUNDING_TABLE:
        raise BfgiError(ErrorCode.INVALID_VALUE, "rounding 必须是 TickRounding 成员", {"rounding": str(rounding)})
    exponent = tick.as_tuple().exponent
    # 运行时不可达：`validate_positive` 已拒绝非有限 tick，有限小数的 exponent 必为 int。
    # 保留该分支是因为 mypy 无法从 `as_tuple()` 的重载推出 int，需要显式窄化（否则 strict 模式报错）。
    if not isinstance(exponent, int):
        raise BfgiError(ErrorCode.INVALID_VALUE, "tickSize 必须是有限小数", {"tick": to_price_str(tick)})
    quantized = price.quantize(Decimal(1).scaleb(exponent), rounding=_ROUNDING_TABLE[rounding])
    if not is_multiple_of_tick(quantized, tick):
        raise BfgiError(
            ErrorCode.INVALID_VALUE,
            "量化后的价格不是 tickSize 的整数倍：tickSize 可能不是 10 的负幂",
            {"price": to_price_str(price), "tick": to_price_str(tick), "quantized": to_price_str(quantized)},
        )
    return quantized
