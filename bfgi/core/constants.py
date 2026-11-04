"""跨模块常量（SYS-004）。

规范禁止散落魔法数字：每个常量必须写明来源文档，业务阈值的调整要走 ADR/BACKLOG（AGENTS.md §10）。
"""

from decimal import Decimal

# ---- 契约与版本身份（ADR-0006 / ADR-0011） ----
SCHEMA_VERSION = "0.1.0-proposal"  # 与 contracts/signal-example.json 一致
MARKET_ID = "binance_usdm_usdt_perpetual"

# ---- 置信度数值映射区间（ADR-0006 §2） ----
# 等级是权威；数值取等级公开区间的中点，仅用于 UI/契约展示，不是概率、不是胜率。
CONFIDENCE_NUMERIC_BANDS: dict[str, tuple[Decimal, Decimal]] = {
    "HIGH": (Decimal("0.75"), Decimal("1.00")),
    "MEDIUM": (Decimal("0.50"), Decimal("0.75")),
    "LOW": (Decimal("0.00"), Decimal("0.50")),
}
CONFIDENCE_IS_PROBABILITY = False
SCORE_IS_PROBABILITY = False

# ---- 有效期（docs/04：valid_until <= as_of + 4h；docs/09 DEFAULT_PLAN_VALID_MINUTES=240） ----
MAX_PLAN_VALID_MINUTES = 240

# ---- 数据可评估性硬闸门（docs/03 覆盖率、docs/04 "<80% 原始 100 分不可评估 → NO_TRADE"） ----
MIN_ASSESSABLE_COVERAGE_PCT = 80

# ---- 评分量程（docs/04：方向 -100..+100，区间 0..100；两者都不是概率） ----
DIRECTION_SCORE_MIN = -100
DIRECTION_SCORE_MAX = 100
RANGE_SCORE_MIN = 0
RANGE_SCORE_MAX = 100

# ---- 调度（ADR-0003：slot 按 15M 对齐；docs/09 MARKET_SCAN_INTERVAL_MINUTES=15） ----
DEFAULT_SCAN_INTERVAL_MINUTES = 15

# ---- 采集并发（docs/02 §6：bounded semaphore 3–5；上限用于配置校验，不是放宽限流的许可） ----
MARKET_REQUEST_CONCURRENCY_RECOMMENDED = (3, 5)
MARKET_REQUEST_CONCURRENCY_HARD_MAX = 8

# ---- 扫描规模分档（docs/03：初筛后 60–100 个标的做多周期计算，精选 20–30 个请求较贵的 OI/主动成交/深度数据） ----
# MAX_MARKET_SYMBOLS_DEEP = 多周期计算档；MAX_DERIVATIVES_SYMBOLS = 精选深数据档。
# ADR-0002 §3 按 "deep 集最多 30 个 symbol（MAX_DERIVATIVES_SYMBOLS=30）" 估算算力，所以 30 这一档挂在 derivatives 上。
MARKET_SYMBOLS_MULTITF_RECOMMENDED = (60, 100)
MARKET_SYMBOLS_MULTITF_HARD_MAX = 100
DERIVATIVES_SYMBOLS_RECOMMENDED = (20, 30)
DERIVATIVES_SYMBOLS_HARD_MAX = 30

# ---- 持久化（ADR-0010：busy_timeout 与保留天数的配置边界，docs/03 retention 7–30 天） ----
SQLITE_BUSY_TIMEOUT_MS_DEFAULT = 5000
DATA_RETENTION_DAYS_RANGE = (7, 30)

# ---- 流动性阈值（docs/03；DATA-006 使用，集中定义避免各处硬编码） ----
MIN_24H_QUOTE_VOLUME_USDT = Decimal("5000000")
MAX_SPREAD_PCT_OF_MID = Decimal("0.15")
MIN_DEPTH_USDT_PER_SIDE_AT_0_5_PCT = Decimal("25000")
QUOTE_FRESHNESS_MAX_SECONDS = 30
