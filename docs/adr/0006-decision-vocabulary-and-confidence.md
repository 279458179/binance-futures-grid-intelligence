# ADR-0006｜统一决策枚举、置信度词汇、阻断码与市场标识

状态：Accepted
日期：2026-11-03
关联任务：SYS-004、SIG-004、GRID-001、API-001、WEB-001

## 背景

任务书与三套参考 skill 用了三套词汇，直接实现会产生"同一个结论两种拼写"：

1. `contracts/signal-example.json`（仓库自身的契约样例，`schema_version: "0.1.0-proposal"`，`example_only: true`，`source: "SYNTHETIC_FIXTURE_NOT_LIVE_MARKET_DATA"`）：`decision`、`entry_state`、`direction_label`、`confidence: "MEDIUM"`、`score_is_probability: false`、`grid.direction`、`data_gaps[]`、`market: "binance_usdm_usdt_perpetual"`。
2. direction-scout 参考：分类 `LONG | SHORT | RANGE | NO_TRADE`，置信度 `HIGH | MEDIUM | LOW`（LOW 不得标注 LONG/SHORT/RANGE）。
3. grid-decision 参考：`decision: NO_TRADE | WATCH | GRID_PLAN | PAUSE_OR_STOP | REVIEW`，并且要求数值型 `confidence: 0.00-1.00`；市场标识写作 `binance_usds_m`。

ACCEPTANCE 的必测场景又写作 `LONG_GRID / SHORT_GRID / NEUTRAL_GRID`（T-01/02/07/08）。若不冻结一套枚举，API、DB、前端、回测会各自造词，回归测试无法比对。

## 决策

**单一权威来源是 `contracts/signal-example.json` 的字段形状**；三套词汇按下表归一，落在 `bfgi/core/enums.py`，由 SYS-004 与 API-001 的契约测试锁定。

### 1. 决策与方向（两层，不混用）

| 字段 | 取值 | 语义来源 |
|---|---|---|
| `decision` | `NO_TRADE` \| `WATCH` \| `GRID_PLAN` \| `PAUSE_OR_STOP` \| `REVIEW` | grid-decision 契约 + 仓库样例 |
| `direction_label` | `LONG` \| `SHORT` \| `RANGE` \| `NONE` | direction-scout 分类（`NO_TRADE` 归入 `decision`，标签写 `NONE`） |
| `grid.direction` | `LONG` \| `SHORT` \| `NEUTRAL` \| `NONE` | 仓库样例；`NONE` 表示本决策不产生网格 |
| `entry_state` | `ENTER_ON_CONFIRMATION` \| `WAIT_PULLBACK` \| `WAIT_BREAKOUT_CLOSE` \| `WAIT_SWEEP_CONFIRMATION` \| `WATCH_ONLY` \| `NO_TRADE` \| `EXPIRED` \| `STALE` | docs/04 入场状态机 |

组合写法（ACCEPTANCE 的 `LONG_GRID` 等）= `decision == GRID_PLAN` 且 `grid.direction == LONG/SHORT/NEUTRAL`。文档与测试断言统一用这个组合表达式，不再新增 `LONG_GRID_PLAN` 之类的复合枚举值。

### 2. 置信度：等级为权威，数值是等级的可读映射

- `confidence`：`HIGH` \| `MEDIUM` \| `LOW`，按 docs/04 定义（|方向分| + 数据覆盖率 + 多周期一致性）判定，**等级不被数值反向改变**。
- `confidence_numeric`：为满足 grid-decision 契约的 0.00–1.00 要求，由等级的**公开区间**推导，取区间中点：
  - `HIGH` → [0.75, 1.00] → 0.875
  - `MEDIUM` → [0.50, 0.75] → 0.625
  - `LOW` → [0.00, 0.50] → 0.25
  - 区间常量集中在 `bfgi/core/constants.py`（单一来源，不散落魔法数字，SYS-004）。
- 两个字段必须同时序列化；`score_is_probability: false`、`confidence_is_probability: false` 固定为 `false`。数值**不是**胜率、不是成交概率、不是收益概率（见 ADR-0008）。
- `LOW` 不得与 `direction_label ∈ {LONG, SHORT, RANGE}` 或 `grid.direction ≠ NONE` 同时出现；`GRID_PLAN` 要求 `confidence ≥ MEDIUM`（grid-scout）。此不变量由 pydantic 模型校验 + 单元测试双向覆盖（合法组合 + 非法组合必须报错）。

### 3. 阻断码 / 数据缺口（两套，不合并）

- `blockers[]`（决策侧，grid-decision 契约的固定清单）：`STALE_DATA`、`BENCHMARK_DOWNTREND`、`BENCHMARK_UPTREND`、`BREAKOUT_SHOCK`、`VOLATILITY_TOO_HIGH`、`FEE_ECONOMICS_FAIL`、`MIN_NOTIONAL_FAIL`、`CAPITAL_RESERVE_FAIL`、`CORRELATED_EXPOSURE_FAIL`、`BAND_STALE`、`INSUFFICIENT_BACKTEST`、`ACCOUNT_DATA_UNAVAILABLE`。
- `data_gaps[]`（数据侧，docs/03 / docs/07）：说明哪一路数据缺失/过期/不一致，例如 `missing_15m_candle`、`funding_history_insufficient`、`depth_snapshot_stale`。
- 规则：`blockers` 解释"为什么不给可执行提案"，`data_gaps` 解释"哪里的数据不可用"；一条 `data_gap` 可以引发一个 `blocker`，但不得用 `data_gaps` 文本代替枚举码，也不得把 `blockers` 塞进 `data_gaps`。

### 4. 市场标识

- 权威值：**`binance_usdm_usdt_perpetual`**（取自仓库自身的 `contracts/signal-example.json`）。
- grid-decision 参考里的 `binance_usds_m` 记为**别名**：解析外部/参考文档格式时接受，落库与出参一律写权威值。避免"两个都支持、输出随机"。

## 后果

- 正面：DB 列、Pydantic 模型、OpenAPI schema、前端类型、回测断言共用一份枚举；契约测试能直接断言非法组合被拒绝；参考 skill 的词汇差异被显式记录而不是靠约定。
- 负面：与 grid-decision 参考的字面拼写不同（`GRID_PLAN` + `grid.direction` 代替 `LONG_GRID_PLAN`，市场标识权威值不同）。缓解：本 ADR 给出映射表，任何引用参考 skill 的文档/测试都必须引用本表。
- 被否决的备选：(a) 直接采用 grid-decision 的 5 值 + 数值置信度并丢弃等级 → 失去 docs/04 的 HIGH/MEDIUM/LOW 定义与"LOW 不得给方向"约束；(b) 保留三套词汇在各自模块 → 契约不可比对。

## 参考判断（jev，模型判断，非已验证事实）

- 等级 vs 数值：`both_grades_primary` 0.83（等级权威、数值派生）。
- 数值派生方式：`grade_band_mapping` 0.84（confidence 0.76），优于 `independent_formula_consistency_gate` 0.16 与 `omit_numeric_entirely` 0.00。
- 前端是否裸显百分比：noul 0.88 支持"数值必须与等级、硬闸门结果和'不是胜率'标签一起出现"。

## 关联

- BACKLOG：SYS-004（schema 版本化、错误码）、SIG-004、GRID-001、API-001（契约与权限负例）、WEB-001
- ACCEPTANCE：新增门禁项"决策/置信度/阻断码枚举一致性测试"
- 相关：ADR-0007（基准耦合）、ADR-0008（分数不是概率）
