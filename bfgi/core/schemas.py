"""决策输出契约（SYS-004 / ADR-0006）。

权威形状来自 `contracts/signal-example.json`；本模块只做两件事：
1. 把 ADR-0006 的枚举与一致性规则变成可执行校验（而不是靠 review 记住）；
2. 守住 docs/02 §7 的 Decimal 边界与 AGENTS.md §5 的降级要求（缺数据必须显式 `data_gaps`）。

注意 ADR-0011 的"版本身份必填"作用在**写入/报告层**：`DecisionRecord.require_version_identity()` 是那道闸门，
契约本体（`contracts/signal-example.json`）不携带这些字段，避免契约样例与存储字段混为一谈。
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, FieldSerializer, field_validator, model_validator

from bfgi.core.constants import (
    CONFIDENCE_IS_PROBABILITY,
    CONFIDENCE_NUMERIC_BANDS,
    DIRECTION_SCORE_MAX,
    DIRECTION_SCORE_MIN,
    MARKET_ID,
    MIN_ASSESSABLE_COVERAGE_PCT,
    RANGE_SCORE_MAX,
    RANGE_SCORE_MIN,
    SCHEMA_VERSION,
)
from bfgi.core.enums import (
    MARKET_ID_ALIASES,
    BlockerCode,
    ConfidenceGrade,
    Decision,
    DirectionLabel,
    EntryState,
    FeeEconomicsStatus,
    GridDirection,
    MarketType,
    BacktestStatus,
    SizingStatus,
    SweepConfirmation,
    SweepType,
)
from bfgi.core.errors import BfgiError, ErrorCode
from bfgi.core.money import to_decimal, to_price_str
from bfgi.core.timeutil import format_utc, is_within_plan_validity, parse_utc

# docs/04 分类阈值：低于这些值不允许给出方向/区间标签（避免"55 分也标 LONG"的漂移）。
DIRECTION_THRESHOLD_LONG = 65
DIRECTION_THRESHOLD_SHORT = -65
RANGE_SCORE_MIN_FOR_RANGE = 70
RANGE_MAX_ABS_DIRECTION_FOR_RANGE = 40

# AGENTS.md §5：fixture/合成数据必须自带标签，不允许冒充真实市场数据。
SOURCE_SYNTHETIC_PREFIX = "SYNTHETIC_FIXTURE"


def _parse_decimal(value: Any) -> Any:
    """价格/金额字段入口：字符串/整数/Decimal 可以，float 与 bool 直接拒绝（docs/02 §7）。"""
    if isinstance(value, Decimal):
        return value
    return to_decimal(value, "decimal_field")


def _dump_decimal(value: Any) -> Any:
    return to_price_str(value) if isinstance(value, Decimal) else value


def _dump_utc(value: Any) -> Any:
    return format_utc(value) if isinstance(value, datetime) else value


DecimalField = Annotated[Decimal, BeforeValidator(_parse_decimal), FieldSerializer(_dump_decimal, mode="json")]
UtcDatetime = Annotated[datetime, BeforeValidator(parse_utc), FieldSerializer(_dump_utc, mode="json")]


class _StrictModel(BaseModel):
    """未知字段直接报错：契约漂移必须在入口暴露，不能被静默忽略。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Zone(_StrictModel):
    """支撑/阻力区域（docs/04：zone 有宽度、记录 timeframe）。"""

    low: DecimalField
    high: DecimalField
    status: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.low > self.high:
            raise _contract("zone 边界倒挂", {"low": to_price_str(self.low), "high": to_price_str(self.high)})
        return self


class SweepEvidence(_StrictModel):
    """扫单/SFP 证据（docs/04 五步阶梯）。步骤 1–3 只能 POSSIBLE 且不构成触发。"""

    type: SweepType
    confirmation: SweepConfirmation
    level: DecimalField | None = None
    extreme: DecimalField | None = None
    mss_confirmed: bool = False

    @model_validator(mode="after")
    def _semantics(self) -> Self:
        if self.confirmation == SweepConfirmation.POSSIBLE and self.mss_confirmed:
            raise _contract("POSSIBLE 扫单不能声称 MSS 已确认（未确认态不得升级）")
        if self.confirmation == SweepConfirmation.CONFIRMED and not self.mss_confirmed:
            raise _contract("CONFIRMED 扫单必须带 MSS/CHOCH 确认")
        if self.level is not None and self.extreme is not None:
            if self.type == SweepType.SSL and self.extreme >= self.level:
                raise _contract("SSL 极值必须低于被扫区域", {"extreme": to_price_str(self.extreme), "level": to_price_str(self.level)})
            if self.type == SweepType.BSL and self.extreme <= self.level:
                raise _contract("BSL 极值必须高于被扫区域", {"extreme": to_price_str(self.extreme), "level": to_price_str(self.level)})
        return self


class GridSection(_StrictModel):
    """网格几何（docs/05）。`fee_economics` 未核验时必须写 NOT_VERIFIED，不能省略。"""

    direction: GridDirection
    lower_bound: DecimalField | None = None
    upper_bound: DecimalField | None = None
    grid_count: int | None = Field(default=None, ge=2)
    fee_economics: FeeEconomicsStatus = FeeEconomicsStatus.NOT_VERIFIED

    @model_validator(mode="after")
    def _geometry(self) -> Self:
        if self.direction == GridDirection.NONE:
            return self
        missing = [
            name
            for name, value in (
                ("lower_bound", self.lower_bound),
                ("upper_bound", self.upper_bound),
                ("grid_count", self.grid_count),
            )
            if value is None
        ]
        if missing:
            raise _contract(f"grid.direction={self.direction} 缺少必要参数", {"missing": missing})
        assert self.lower_bound is not None and self.upper_bound is not None
        if self.lower_bound >= self.upper_bound:
            raise _contract("grid 下界必须低于上界")
        return self


class RiskSection(_StrictModel):
    """风险参数。资金未知时 `max_loss_usdt` 必须是 null 且 `sizing_status` 不是 CALCULATED（AGENTS.md §5）。"""

    take_profit_1: DecimalField | None = None
    take_profit_2: DecimalField | None = None
    stop_loss: DecimalField | None = None
    max_loss_usdt: DecimalField | None = None
    sizing_status: SizingStatus = SizingStatus.NOT_CALCULATED

    @model_validator(mode="after")
    def _sizing(self) -> Self:
        if self.sizing_status == SizingStatus.NOT_CALCULATED and self.max_loss_usdt is not None:
            raise _contract("sizing_status=NOT_CALCULATED 不能给出 max_loss_usdt")
        if self.sizing_status == SizingStatus.CALCULATED and self.max_loss_usdt is None:
            raise _contract("sizing_status=CALCULATED 必须给出 max_loss_usdt")
        return self


class BacktestSection(_StrictModel):
    """回测状态（docs/06）。未运行就写 NOT_RUN，不允许空着或给数字。"""

    days_7: BacktestStatus = BacktestStatus.NOT_RUN
    days_30: BacktestStatus = BacktestStatus.NOT_RUN


def _contract(message: str, details: Mapping[str, Any] | None = None) -> ValueError:
    """统一契约错误：内部用 BfgiError 语义，pydantic 需要 ValueError 才能汇总到 ValidationError。"""
    return ValueError(f"{message}{f' ({details})' if details else ''}")


def confidence_numeric_for_grade(grade: ConfidenceGrade) -> Decimal:
    """ADR-0006 §2：取等级公开区间的中点。等级是权威，数值只是可读映射，不是概率。"""
    lo, hi = CONFIDENCE_NUMERIC_BANDS[grade.value]
    return ((lo + hi) / 2).quantize(Decimal("0.001"))


class DecisionRecord(_StrictModel):
    """单品种决策记录（docs/07 契约）。"""

    schema_version: str = SCHEMA_VERSION
    example_only: bool = False
    source: str = Field(min_length=3)
    scan_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.:\-]+$")
    as_of_utc: UtcDatetime
    valid_until_utc: UtcDatetime
    symbol: str
    market: MarketType = MarketType.BINANCE_USDM_USDT_PERPETUAL
    decision: Decision
    entry_state: EntryState
    direction_label: DirectionLabel
    direction_score: int = Field(ge=DIRECTION_SCORE_MIN, le=DIRECTION_SCORE_MAX)
    range_score: int = Field(ge=RANGE_SCORE_MIN, le=RANGE_SCORE_MAX)
    confidence: ConfidenceGrade
    confidence_numeric: Decimal | None = None
    score_is_probability: bool = False
    confidence_is_probability: bool = CONFIDENCE_IS_PROBABILITY
    data_coverage_pct: int = Field(ge=0, le=100)
    blockers: list[BlockerCode] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    support_zones: list[Zone] = Field(default_factory=list)
    resistance_zones: list[Zone] = Field(default_factory=list)
    sweep: SweepEvidence | None = None
    signal_trigger: str | None = None
    activation_price: DecimalField | None = None
    activation_semantics_verified: bool = False
    entry_zone: Zone | None = None
    grid: GridSection = Field(default_factory=lambda: GridSection(direction=GridDirection.NONE))
    risk: RiskSection = Field(default_factory=RiskSection)
    backtest: BacktestSection = Field(default_factory=BacktestSection)
    orders_placed: bool = False

    @field_validator("schema_version")
    @classmethod
    def _schema_version_known(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise _contract(f"schema_version 必须是 {SCHEMA_VERSION}", {"got": value})
        return value

    @field_validator("symbol")
    @classmethod
    def _symbol_shape(cls, value: str) -> str:
        symbol = value.strip().upper()
        # docs/03：只接受 quoteAsset=USDT 的合约。
        if not symbol or len(symbol) > 24 or not symbol.endswith("USDT"):
            raise _contract("symbol 必须是 USDT 报价合约代码", {"symbol": value})
        return symbol

    @field_validator("market", mode="before")
    @classmethod
    def _normalize_market(cls, value: Any) -> Any:
        if isinstance(value, MarketType):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in MARKET_ID_ALIASES:
                return MARKET_ID_ALIASES[text]
            if text == MARKET_ID:
                return MarketType.BINANCE_USDM_USDT_PERPETUAL
        raise _contract("market 不受支持", {"market": value})

    @field_validator("score_is_probability", "confidence_is_probability")
    @classmethod
    def _must_be_false(cls, value: bool) -> bool:
        if value:
            raise _contract("分数与置信度不是概率，不能标成概率")
        return value

    @field_validator("orders_placed")
    @classmethod
    def _no_orders(cls, value: bool) -> bool:
        if value:
            # ADR-0009：本系统不产生订单。出现 true 说明有代码越界。
            raise ValueError("orders_placed 必须为 false：系统只读，不执行任何订单")
        return value

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        self._fill_confidence_numeric()
        self._check_time_window()
        self._check_source_label()
        self._check_data_gaps_not_blockers()
        self._check_thresholds_match_labels()
        self._check_decision_matrix()
        self._check_coverage_gate()
        self._check_activation_gap()
        self._check_stop_loss_for_plan()
        return self

    # ---- ADR-0006：confidence 与 confidence_numeric 必须同时存在 ----
    def _fill_confidence_numeric(self) -> None:
        expected = confidence_numeric_for_grade(self.confidence)
        if self.confidence_numeric is None:
            object.__setattr__(self, "confidence_numeric", expected)
            return
        lo, hi = CONFIDENCE_NUMERIC_BANDS[self.confidence.value]
        if not lo <= self.confidence_numeric <= hi:
            raise _contract(
                "confidence_numeric 与 confidence 等级不一致",
                {"confidence": self.confidence.value, "numeric": to_price_str(self.confidence_numeric)},
            )

    def _check_time_window(self) -> None:
        if not is_within_plan_validity(self.as_of_utc, self.valid_until_utc):
            raise _contract(
                "有效期必须满足 0 < valid_until - as_of <= 240 分钟（docs/04）",
                {"as_of": format_utc(self.as_of_utc), "valid_until": format_utc(self.valid_until_utc)},
            )

    def _check_source_label(self) -> None:
        if self.source.startswith(SOURCE_SYNTHETIC_PREFIX) and not self.example_only:
            raise _contract("合成/fixture 数据必须标 example_only=true，不能冒充真实市场数据（AGENTS.md §5）")

    def _check_data_gaps_not_blockers(self) -> None:
        # ADR-0006：blockers 与 data_gaps 两套语义不得混用。
        blocker_values = {code.value for code in BlockerCode}
        overlap = sorted({gap for gap in self.data_gaps if gap in blocker_values})
        if overlap:
            raise _contract("data_gaps 不能填 BlockerCode 值", {"overlap": overlap})
        if self.blockers and self.decision == Decision.GRID_PLAN:
            raise _contract("存在阻断码时不能给出 GRID_PLAN", {"blockers": [b.value for b in self.blockers]})
        if self.decision == Decision.NO_TRADE and not (self.blockers or self.data_gaps):
            raise _contract("NO_TRADE 必须给出理由：blockers 或 data_gaps 至少其一非空")

    def _check_thresholds_match_labels(self) -> None:
        if self.direction_label == DirectionLabel.LONG and self.direction_score < DIRECTION_THRESHOLD_LONG:
            raise _contract(f"LONG 标签要求 direction_score >= {DIRECTION_THRESHOLD_LONG}", {"direction_score": self.direction_score})
        if self.direction_label == DirectionLabel.SHORT and self.direction_score > DIRECTION_THRESHOLD_SHORT:
            raise _contract(f"SHORT 标签要求 direction_score <= {DIRECTION_THRESHOLD_SHORT}", {"direction_score": self.direction_score})
        if self.direction_label == DirectionLabel.RANGE:
            if self.range_score < RANGE_SCORE_MIN_FOR_RANGE:
                raise _contract(f"RANGE 标签要求 range_score >= {RANGE_SCORE_MIN_FOR_RANGE}", {"range_score": self.range_score})
            if abs(self.direction_score) >= RANGE_MAX_ABS_DIRECTION_FOR_RANGE:
                raise _contract(f"RANGE 标签要求 |direction_score| < {RANGE_MAX_ABS_DIRECTION_FOR_RANGE}", {"direction_score": self.direction_score})

    def _check_decision_matrix(self) -> None:
        # ADR-0006：LOW 不得与方向标签或网格方向同时出现。
        if self.confidence == ConfidenceGrade.LOW and (
            self.direction_label != DirectionLabel.NONE or self.grid.direction != GridDirection.NONE
        ):
            raise _contract("LOW 置信度不得给出 LONG/SHORT/RANGE 标签或网格方向")

        if self.grid.direction != GridDirection.NONE and self.decision != Decision.GRID_PLAN:
            raise _contract("给出网格方向必须伴随 GRID_PLAN", {"decision": self.decision.value})
        if self.decision in {Decision.NO_TRADE, Decision.WATCH, Decision.REVIEW} and self.grid.direction != GridDirection.NONE:
            raise _contract(f"decision={self.decision.value} 不应携带网格方向")
        if self.decision == Decision.GRID_PLAN:
            if self.confidence == ConfidenceGrade.LOW:
                raise _contract("GRID_PLAN 要求 confidence >= MEDIUM")
            if not self.signal_trigger:
                raise _contract("GRID_PLAN 必须给出 signal_trigger（docs/05：一个价格数字不是入场触发）")
            if self.entry_state in {EntryState.NO_TRADE, EntryState.EXPIRED, EntryState.STALE, EntryState.WATCH_ONLY}:
                raise _contract(f"entry_state={self.entry_state.value} 与 GRID_PLAN 冲突")
        if self.entry_state in {EntryState.EXPIRED, EntryState.STALE} and self.decision == Decision.GRID_PLAN:
            raise _contract("过期/陈旧的入场状态不能给出可执行网格计划")
        if self.entry_state == EntryState.STALE and BlockerCode.STALE_DATA not in self.blockers:
            raise _contract("entry_state=STALE 必须带 STALE_DATA 阻断码")

    def _check_coverage_gate(self) -> None:
        # docs/04：可评估覆盖 < 80% → 硬闸门 NO_TRADE，并显式披露缺口。
        if self.data_coverage_pct < MIN_ASSESSABLE_COVERAGE_PCT:
            if self.decision != Decision.NO_TRADE:
                raise _contract(
                    f"coverage {self.data_coverage_pct}% < {MIN_ASSESSABLE_COVERAGE_PCT}% 必须 NO_TRADE",
                    {"coverage_pct": self.data_coverage_pct},
                )
            if not self.data_gaps:
                raise _contract("覆盖不足必须写进 data_gaps")

    def _check_activation_gap(self) -> None:
        # docs/05：平台启动语义未核验时，GRID_PLAN 必须显式披露需要人工管理。
        if self.decision == Decision.GRID_PLAN and not self.activation_semantics_verified and not self.data_gaps:
            raise _contract("GRID_PLAN 且 activation_semantics_verified=false 时必须写 data_gaps")

    def _check_stop_loss_for_plan(self) -> None:
        if self.decision != Decision.GRID_PLAN:
            return
        if self.risk.stop_loss is None:
            raise _contract("GRID_PLAN 必须给出 stop_loss/invalidation_price（docs/05）")
        if self.grid.fee_economics == FeeEconomicsStatus.NOT_VERIFIED:
            raise _contract("GRID_PLAN 要求费用经济性至少是 ASSUMED（docs/06 假设披露）")
        self._check_stop_outside_band()

    def _check_stop_outside_band(self) -> None:
        stop = self.risk.stop_loss
        if stop is None or self.grid.lower_bound is None or self.grid.upper_bound is None:
            return
        # 止损必须落在网格区间之外，否则网格每轮都会自我触发止损。
        if self.grid.direction == GridDirection.LONG and stop >= self.grid.lower_bound:
            raise _contract("LONG 网格止损必须低于 grid_lower_bound")
        if self.grid.direction == GridDirection.SHORT and stop <= self.grid.upper_bound:
            raise _contract("SHORT 网格止损必须高于 grid_upper_bound")

    def require_version_identity(self, identity: Mapping[str, Any]) -> None:
        """ADR-0011：写入/报告前必须绑定版本身份。契约样例本身不携带这些字段。"""
        required = ("strategy_version", "git_commit", "market_data_hash", "schema_version")
        missing = [name for name in required if not str(identity.get(name) or "").strip()]
        if missing:
            raise BfgiError(ErrorCode.CONTRACT_VIOLATION, "版本身份字段缺失（ADR-0011）", {"missing": missing})
        if identity["schema_version"] != self.schema_version:
            raise BfgiError(
                ErrorCode.CONTRACT_VIOLATION,
                "版本身份的 schema_version 与记录不一致",
                {"identity": identity["schema_version"], "record": self.schema_version},
            )
