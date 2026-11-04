"""契约与基础设施层（ADR-0001）。

这里只有 DTO/契约、错误码、时间与 Decimal 规则、哈希与版本身份、配置——不依赖任何网络层或存储层。
`bfgi/core` 允许的外部依赖只有标准库与 pydantic（由 tests/architecture/test_dependency_direction.py 强制）。
"""

from bfgi.core.version import STRATEGY_VERSION

__all__ = ["STRATEGY_VERSION"]
