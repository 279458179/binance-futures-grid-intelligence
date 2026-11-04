"""错误码与异常基类（SYS-004）。

docs/02 §7 / docs/08：错误结构必须稳定且语义化；docs/03 §限流：429/418/451/5xx 必须区分处理，
且不得通过轮换身份/跨区域绕过（docs/09）。HTTP 状态到内部错误码的映射集中在这里，避免各处自行翻译。
"""

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """内部稳定错误码。对外 API 错误结构（API-001）只暴露 `code` + `message`，不透传内部细节。"""

    # 输入 / 契约
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_TIME = "INVALID_TIME"
    INVALID_DECIMAL = "INVALID_DECIMAL"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    CONFIG_ERROR = "CONFIG_ERROR"
    READ_ONLY_VIOLATION = "READ_ONLY_VIOLATION"

    # 数据质量
    STALE_DATA = "STALE_DATA"
    DATA_GAP = "DATA_GAP"

    # 交易所 / 数据源（docs/03：429 尊重 Retry-After；418 停止并上报；不绕限流）
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_BANNED = "PROVIDER_BANNED"
    PROVIDER_GEO_BLOCKED = "PROVIDER_GEO_BLOCKED"
    PROVIDER_SERVER_ERROR = "PROVIDER_SERVER_ERROR"
    PROVIDER_CLIENT_ERROR = "PROVIDER_CLIENT_ERROR"
    PROVIDER_TRANSPORT_ERROR = "PROVIDER_TRANSPORT_ERROR"
    PROVIDER_SCHEMA_DRIFT = "PROVIDER_SCHEMA_DRIFT"


class BfgiError(Exception):
    """所有领域错误的基类。`code` 稳定可被 API/日志消费；`details` 不得包含密钥或凭据。"""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "details": self.details}


def http_status_to_error_code(status: int) -> ErrorCode:
    """把 HTTP 状态映射到内部错误码（docs/03 §限流与错误处理）。

    451 是地理限制：只能如实上报并降级，禁止用身份/区域轮换绕过（docs/09）。
    """
    if status == 429:
        return ErrorCode.PROVIDER_RATE_LIMITED
    if status == 418:
        return ErrorCode.PROVIDER_BANNED
    if status == 451:
        return ErrorCode.PROVIDER_GEO_BLOCKED
    if 500 <= status <= 599:
        return ErrorCode.PROVIDER_SERVER_ERROR
    if 400 <= status <= 499:
        return ErrorCode.PROVIDER_CLIENT_ERROR
    return ErrorCode.PROVIDER_TRANSPORT_ERROR


def is_retryable_status(status: int) -> bool:
    """是否允许有限重试（docs/03：5xx 有限重试 + 熔断；429 按 Retry-After；418/451 不重试）。"""
    return status == 429 or 500 <= status <= 599
