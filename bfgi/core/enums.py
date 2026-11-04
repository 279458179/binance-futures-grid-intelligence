"""决策词汇的唯一权威来源（ADR-0006）。

字段形状权威来源是 `contracts/signal-example.json`；三套参考 skill 的词汇差异按 ADR-0006 的映射表归一，
冲突一律按更严格的风险边界解释（AGENTS.md §3）。任何新增/改名都必须先更新 ADR-0006 或 BACKLOG。
"""

from enum import StrEnum

# ---------------------------------------------------------------- 决策 / 方向


class Decision(StrEnum):
    """决策结论。grid-decision 契约的 5 值（ADR-0006 §1）。"""

    NO_TRADE = "NO_TRADE"
    WATCH = "WATCH"
    GRID_PLAN = "GRID_PLAN"
    PAUSE_OR_STOP = "PAUSE_OR_STOP"
    REVIEW = "REVIEW"


class DirectionLabel(StrEnum):
    """direction-scout 的分类标签。`NO_TRADE` 属于 `decision`，标签写 `NONE`。"""

    LONG = "LONG"
    SHORT = "SHORT"
    RANGE = "RANGE"
    NONE = "NONE"


class GridDirection(StrEnum):
    """网格方向。`NONE` 表示本决策不产生网格。"""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
    NONE = "NONE"


class EntryState(StrEnum):
    """docs/04 入场状态机（含失效态）。"""

    ENTER_ON_CONFIRMATION = "ENTER_ON_CONFIRMATION"
    WAIT_PULLBACK = "WAIT_PULLBACK"
    WAIT_BREAKOUT_CLOSE = "WAIT_BREAKOUT_CLOSE"
    WAIT_SWEEP_CONFIRMATION = "WAIT_SWEEP_CONFIRMATION"
    WATCH_ONLY = "WATCH_ONLY"
    NO_TRADE = "NO_TRADE"
    EXPIRED = "EXPIRED"
    STALE = "STALE"


class ConfidenceGrade(StrEnum):
    """置信度等级（权威）。数值 `confidence_numeric` 只是等级的可读映射（ADR-0006 §2）。"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------------- 阻断 / 数据缺口


class BlockerCode(StrEnum):
    """决策侧阻断码（grid-decision 契约固定清单，ADR-0006 §3）。

    解释"为什么不给可执行提案"；不得与 `data_gaps` 混用。
    """

    STALE_DATA = "STALE_DATA"
    BENCHMARK_DOWNTREND = "BENCHMARK_DOWNTREND"
    BENCHMARK_UPTREND = "BENCHMARK_UPTREND"
    BREAKOUT_SHOCK = "BREAKOUT_SHOCK"
    VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"
    FEE_ECONOMICS_FAIL = "FEE_ECONOMICS_FAIL"
    MIN_NOTIONAL_FAIL = "MIN_NOTIONAL_FAIL"
    CAPITAL_RESERVE_FAIL = "CAPITAL_RESERVE_FAIL"
    CORRELATED_EXPOSURE_FAIL = "CORRELATED_EXPOSURE_FAIL"
    BAND_STALE = "BAND_STALE"
    INSUFFICIENT_BACKTEST = "INSUFFICIENT_BACKTEST"
    ACCOUNT_DATA_UNAVAILABLE = "ACCOUNT_DATA_UNAVAILABLE"


class ScanStatus(StrEnum):
    """数据完整性状态（docs/03：缺口/过期/盘口异常 → PARTIAL/STALE，不得回填陈旧价格）。"""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"


class BacktestStatus(StrEnum):
    """回测状态（ADR-0011 §4）。只有 COMPLETED 才允许引用其指标。"""

    NOT_RUN = "NOT_RUN"
    NOT_VALIDATED = "NOT_VALIDATED"
    COMPLETED = "COMPLETED"


class PrimaryCause(StrEnum):
    """失败归因分类（grid-decision 参考，ADR-0011 §3）。只允许一个 primary cause。"""

    REGIME_ERROR = "REGIME_ERROR"
    BAND_ERROR = "BAND_ERROR"
    GRID_DENSITY_ERROR = "GRID_DENSITY_ERROR"
    LEVERAGE_ERROR = "LEVERAGE_ERROR"
    CAPITAL_FEASIBILITY_ERROR = "CAPITAL_FEASIBILITY_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    DISCIPLINE_ERROR = "DISCIPLINE_ERROR"
    EXTERNAL_SHOCK = "EXTERNAL_SHOCK"


class RegimeLabel(StrEnum):
    """基准/品种 regime 标签（grid-decision 契约）。BREAKOUT_SHOCK / UNCERTAIN 一律不进入可执行提案。"""

    RANGE = "RANGE"
    UPTREND_PULLBACK = "UPTREND_PULLBACK"
    DOWNTREND_REBOUND = "DOWNTREND_REBOUND"
    BREAKOUT_SHOCK = "BREAKOUT_SHOCK"
    UNCERTAIN = "UNCERTAIN"


# ---------------------------------------------------------------- 结构 / 证据


class SweepType(StrEnum):
    """扫单方向（docs/04：BSL/SSL 是概念区域，不声称精确止损位置或机构意图）。"""

    BSL = "BSL"
    SSL = "SSL"


class SweepConfirmation(StrEnum):
    """扫单确认状态（docs/04 五步阶梯；步骤 1–3 只能给 POSSIBLE，不构成触发）。"""

    NOT_PRESENT = "NOT_PRESENT"
    POSSIBLE = "POSSIBLE"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class SizingStatus(StrEnum):
    """仓位可算性（docs/05：资金/费率未知必须降级）。

    `NOT_CALCULATED` / `PARTIAL` 取自 docs/05 与契约样例；`CALCULATED` 是"资金与费率已知"一侧的补齐拼写，
    由 GRID-006 冻结前视为待核验。
    """

    CALCULATED = "CALCULATED"
    PARTIAL = "PARTIAL"
    NOT_CALCULATED = "NOT_CALCULATED"


class FeeEconomicsStatus(StrEnum):
    """单格费用经济性核验状态（docs/06 要求披露费用/滑点假设）。

    `NOT_VERIFIED` 取自契约样例；`ASSUMED` 表示用了显式披露的假设费率，`VERIFIED` 表示用交易所实时 filter/费率核验。
    """

    NOT_VERIFIED = "NOT_VERIFIED"
    ASSUMED = "ASSUMED"
    VERIFIED = "VERIFIED"


# ---------------------------------------------------------------- 事件 / 审计


class AlertEventKind(StrEnum):
    """docs/07 事件类型。"""

    NEW_SETUP_WATCH = "NEW_SETUP_WATCH"
    ENTRY_CONDITION_CONFIRMED = "ENTRY_CONDITION_CONFIRMED"
    PLAN_INVALIDATED = "PLAN_INVALIDATED"
    PLAN_EXPIRED = "PLAN_EXPIRED"
    RISK_ALERT = "RISK_ALERT"
    DATA_DEGRADED = "DATA_DEGRADED"


class MarketType(StrEnum):
    """市场标识（ADR-0006 §4）。权威值只有一个，别名只在解析入参时接受。"""

    BINANCE_USDM_USDT_PERPETUAL = "binance_usdm_usdt_perpetual"


MARKET_ID_ALIASES: dict[str, MarketType] = {
    "binance_usds_m": MarketType.BINANCE_USDM_USDT_PERPETUAL,
    "binance_usdm_usdt_perpetual": MarketType.BINANCE_USDM_USDT_PERPETUAL,
}
