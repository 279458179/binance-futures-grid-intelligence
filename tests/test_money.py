"""SYS-004 冻结测试：Decimal 纪律与 tick 量化（docs/02 §7、docs/05）。

覆盖三类已知风险：
- float 进入价格路径（docs/02 §7 明确禁止）；
- 非有限 Decimal（NaN/Inf）被当成合法正数放行，随后在 divmod/quantize 里泄漏底层
  `decimal.InvalidOperation`（SYS-004 复测发现的根因）；
- tick 不是 10 的负幂时量化结果并非 tick 的整数倍。

错误码约定（与 bfgi/core/errors.py 的 taxonomy 一致，复测后确认，不是为了让测试通过而放宽）：
- INVALID_DECIMAL = 字段不是合法/有限的 Decimal（float、NaN、±Infinity、脏字符串、非 Decimal 类型）；
- INVALID_VALUE = 数值合法但落在允许范围之外（0、负数、超出 tick 精度、places < 0）。
因此 tickSize = 0 与 tickSize < 0 属于 INVALID_VALUE（范围问题），tickSize = NaN 属于 INVALID_DECIMAL（有限性问题）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bfgi.core.errors import BfgiError, ErrorCode
from bfgi.core.money import (
    TickRounding,
    decimal_from_float,
    is_multiple_of_tick,
    quantize_to_tick,
    to_decimal,
    to_price_str,
    validate_positive,
)


def error_code_of(call, *args) -> ErrorCode:
    with pytest.raises(BfgiError) as excinfo:
        call(*args)
    return excinfo.value.code


# ---------------------------------------------------------------- to_decimal

def test_to_decimal_accepts_int_decimal_and_string() -> None:
    assert to_decimal(1, "price") == Decimal("1")
    assert to_decimal(Decimal("1.23"), "price") == Decimal("1.23")
    assert to_decimal(" 1.230 ", "price") == Decimal("1.230")
    # 科学计数法输入合法（有效位数只有 1 位）
    assert to_decimal("1E50", "price") == Decimal("1E50")


@pytest.mark.parametrize("value", [1.23, 0.1, float("nan"), float("inf")])
def test_to_decimal_rejects_float(value: float) -> None:
    assert error_code_of(to_decimal, value, "price") is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize("value", [True, False])
def test_to_decimal_rejects_bool(value: bool) -> None:
    assert error_code_of(to_decimal, value, "price") is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize("value", ["", "   ", "abc", "1,23", "1.2.3"])
def test_to_decimal_rejects_bad_strings(value: str) -> None:
    assert error_code_of(to_decimal, value, "price") is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_to_decimal_rejects_non_finite_decimal(value: Decimal) -> None:
    assert error_code_of(to_decimal, value, "price") is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize("value", [None, [], {}, object()])
def test_to_decimal_rejects_unsupported_types(value: object) -> None:
    assert error_code_of(to_decimal, value, "price") is ErrorCode.INVALID_DECIMAL


def test_to_decimal_rejects_absurd_precision() -> None:
    """脏数据在入口挡掉，而不是留给下游算成荒谬网格。"""
    assert error_code_of(to_decimal, "1234567890123456789012345678901.1", "price") is ErrorCode.INVALID_DECIMAL


# ---------------------------------------------------------------- decimal_from_float

def test_decimal_from_float_is_the_explicit_escape_hatch() -> None:
    assert decimal_from_float(1.23456, 2, "avg") == Decimal("1.23")
    assert decimal_from_float(0.1 + 0.2, 4, "avg") == Decimal("0.3000")


@pytest.mark.parametrize("value", [True, 1, "1.23", None])
def test_decimal_from_float_rejects_non_float(value: object) -> None:
    assert error_code_of(decimal_from_float, value, 2, "avg") is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_decimal_from_float_rejects_non_finite(value: float) -> None:
    assert error_code_of(decimal_from_float, value, 2, "avg") is ErrorCode.INVALID_DECIMAL


def test_decimal_from_float_rejects_negative_places() -> None:
    assert error_code_of(decimal_from_float, 1.23, -1, "avg") is ErrorCode.INVALID_VALUE


# ---------------------------------------------------------------- to_price_str

def test_to_price_str_avoids_scientific_notation() -> None:
    assert to_price_str(Decimal("1E50")) == "1" + "0" * 50
    assert to_price_str(Decimal("0.00010")) == "0.00010"


def test_to_price_str_rejects_non_decimal_and_nan() -> None:
    assert error_code_of(to_price_str, "1.23") is ErrorCode.INVALID_DECIMAL
    assert error_code_of(to_price_str, Decimal("NaN")) is ErrorCode.INVALID_DECIMAL


# ---------------------------------------------------------------- validate_positive

def test_validate_positive_accepts_positive_finite() -> None:
    assert validate_positive(Decimal("0.00001"), "tickSize") == Decimal("0.00001")


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1"), Decimal("-0.00001")])
def test_validate_positive_rejects_non_positive(value: Decimal) -> None:
    assert error_code_of(validate_positive, value, "tickSize") is ErrorCode.INVALID_VALUE


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_validate_positive_rejects_non_finite(value: Decimal) -> None:
    """回归：`Decimal('NaN') <= 0` 为 False，旧实现会把 NaN 当成合法正数放行。"""
    assert error_code_of(validate_positive, value, "tickSize") is ErrorCode.INVALID_DECIMAL


def test_validate_positive_rejects_non_decimal() -> None:
    assert error_code_of(validate_positive, 1.5, "tickSize") is ErrorCode.INVALID_DECIMAL


# ---------------------------------------------------------------- is_multiple_of_tick

@pytest.mark.parametrize(
    ("value", "tick", "expected"),
    [
        (Decimal("1.23"), Decimal("0.01"), True),
        (Decimal("1.235"), Decimal("0.01"), False),
        (Decimal("0"), Decimal("0.01"), True),
        (Decimal("-1.23"), Decimal("0.01"), False),
        (Decimal("1"), Decimal("0.1"), True),
    ],
)
def test_is_multiple_of_tick(value: Decimal, tick: Decimal, expected: bool) -> None:
    assert is_multiple_of_tick(value, tick) is expected


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_is_multiple_of_tick_rejects_non_finite_value(value: Decimal) -> None:
    assert error_code_of(is_multiple_of_tick, value, Decimal("0.01")) is ErrorCode.INVALID_DECIMAL


@pytest.mark.parametrize(
    ("tick", "expected"),
    [
        (Decimal("0"), ErrorCode.INVALID_VALUE),
        (Decimal("-0.01"), ErrorCode.INVALID_VALUE),
        (Decimal("NaN"), ErrorCode.INVALID_DECIMAL),
    ],
)
def test_is_multiple_of_tick_rejects_bad_tick(tick: Decimal, expected: ErrorCode) -> None:
    assert error_code_of(is_multiple_of_tick, Decimal("1.23"), tick) is expected


# ---------------------------------------------------------------- quantize_to_tick

def test_quantize_default_is_half_up() -> None:
    assert quantize_to_tick(Decimal("1.235"), Decimal("0.01")) == Decimal("1.24")
    assert quantize_to_tick(Decimal("1.234"), Decimal("0.01")) == Decimal("1.23")


def test_quantize_directions_are_asymmetric() -> None:
    """入场与止损的保守方向不同，必须由调用方显式选择。"""
    assert quantize_to_tick(Decimal("1.231"), Decimal("0.01"), TickRounding.CEILING) == Decimal("1.24")
    assert quantize_to_tick(Decimal("1.239"), Decimal("0.01"), TickRounding.FLOOR) == Decimal("1.23")


def test_quantize_rejects_negative_price_with_price_related_message() -> None:
    """回归：负价格过去会走到"tickSize 可能不是 10 的负幂"，把排障方向指向 tick 而不是输入。"""
    with pytest.raises(BfgiError) as excinfo:
        quantize_to_tick(Decimal("-1.239"), Decimal("0.01"), TickRounding.FLOOR)
    assert excinfo.value.code is ErrorCode.INVALID_VALUE
    assert "tickSize" not in str(excinfo.value)
    assert excinfo.value.details["field"] == "price"


def test_quantize_honours_coarser_ticks() -> None:
    assert quantize_to_tick(Decimal("64321.7"), Decimal("0.1")) == Decimal("64321.7")
    assert quantize_to_tick(Decimal("64321.7"), Decimal("1")) == Decimal("64322")


@pytest.mark.parametrize(
    ("tick", "expected"),
    [
        (Decimal("0"), ErrorCode.INVALID_VALUE),
        (Decimal("-0.01"), ErrorCode.INVALID_VALUE),
        (Decimal("NaN"), ErrorCode.INVALID_DECIMAL),
        (Decimal("Infinity"), ErrorCode.INVALID_DECIMAL),
    ],
)
def test_quantize_rejects_bad_tick(tick: Decimal, expected: ErrorCode) -> None:
    assert error_code_of(quantize_to_tick, Decimal("1.234"), tick) is expected


@pytest.mark.parametrize("price", [Decimal("NaN"), Decimal("Infinity")])
def test_quantize_rejects_non_finite_price(price: Decimal) -> None:
    assert error_code_of(quantize_to_tick, price, Decimal("0.01")) is ErrorCode.INVALID_DECIMAL


def test_quantize_rejects_tick_that_is_not_a_power_of_ten() -> None:
    """1.25 量化到 2 位后不是 0.03 的整数倍：说明 tick 本身是脏数据，必须报错而不是近似。"""
    assert error_code_of(quantize_to_tick, Decimal("1.25"), Decimal("0.03")) is ErrorCode.INVALID_VALUE
