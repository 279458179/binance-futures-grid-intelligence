# ADR-0007｜基准耦合闸门取两套规则的并集，相对强弱例外不解除网格阻断

状态：Accepted
日期：2026-11-03
关联任务：SIG-001、SIG-004、GRID-006、RISK（bfgi/risk）

## 背景

两套参考对"BTC/ETH 背景与山寨币网格的关系"给了不同强度的表述：

1. direction-scout（评分层）：硬闸门"BTC 与 ETH 同时强烈反对该山寨币 → NO_TRADE"，但存在**相对强弱例外**（候选在 4h 与 24h 上均跑赢 BTC ≥1.0pp 时，基准项不扣分，闸门可放行）。基准项满分 5 分同样只在 BTC **和** ETH 一致时给分，否则 0 分并解释。
2. grid-decision（风控层）：具体阈值化的耦合守卫——当两个基准**同时**满足 `1H close < EMA20`、`1H close < EMA50` 或 `EMA20` 明显下弯且位于 `EMA50` 之下、`1H RSI < 45`、`3h 收益率 < 0`（默认不设例外）时，**阻止新开山寨币 LONG 和 NEUTRAL 网格**，阻断码 `BENCHMARK_DOWNTREND`（镜像条件阻止 SHORT，码 `BENCHMARK_UPTREND`）。

AGENTS.md §3 要求冲突按**更严格的风险边界**解释并在 ADR 留痕。

## 决策

`bfgi/risk/benchmark_guard.py` 实现两套条件，**取并集，任一命中即阻断**：

1. **定性条件（direction-scout）**：BTC 与 ETH 的 4H/1H 背景同时强烈反对候选方向 → 决策层硬闸门，`NO_TRADE`。
2. **定量条件（grid-decision）**：上表 4 个阈值对两个基准同时成立 → 网格层阻断，`blockers: [BENCHMARK_DOWNTREND]`（或 `BENCHMARK_UPTREND`），对 `grid.direction == LONG/SHORT/NEUTRAL` 全部生效。
3. **例外边界**：相对强弱例外**只作用于评分层**（可恢复基准项的 5 分、可放行定性硬闸门），**不解除**网格层的定量耦合守卫。即：一个"跑赢 BTC"的山寨币可以在报告里拿到更高的方向分，但在定量耦合守卫命中时 `decision` 仍是 `WATCH` 或 `NO_TRADE`，不给 `GRID_PLAN`。这是更保守的一侧，代价是漏掉部分强势山寨币机会——按 §3 接受。
4. 守卫输出必须是可解释结构：`{state: BLOCK|ALLOW|UNCERTAIN, fired: [规则 id], evidence: {btc/eth: {ema20, ema50, rsi1h, ret_3h, close}}, benchmark_as_of_utc}`，缺任一基准数据 → `state: UNCERTAIN` → 按阻断处理（docs/03：关键源缺失即降级）。
5. 基准背景分（5 分）与耦合守卫是两条独立代码路径：前者只影响分数，后者只影响 `decision`/`blockers`；不得把守卫结果折算成分数扣分。

## 后果

- 正面：不会因为"某一侧规则写得更具体"而放松另一侧；山寨币在 BTC/ETH 双弱背景下的 LONG 与 NEUTRAL 都被挡住（NEUTRAL 也挡，这是 grid-decision 明确要求，且比 direction-scout 更严）。
- 负面：更保守 → 更多 `WATCH/NO_TRADE`，实盘机会减少；两套条件可能在同一案例上给出不同 `fired` 集合，需要在 UI 上同时展示。风险可控：漏掉机会不产生损失，错误放行才产生损失。
- 被否决的备选：只实现定量守卫（丢失定性判断与相对强弱例外）；只实现定性闸门（无法给出可审计阈值与阻断码）；例外同时解除网格阻断（更宽松，违反 §3）。

## 参考判断（jev，模型判断，非已验证事实）

`union_stricter` 0.95（取并集、更严格一侧胜出）。作为选型输入；结论仍由 AGENTS.md §3 的严格性规则决定。

## 关联

- ACCEPTANCE：T-09（BTC/ETH 强空、山寨仅 15M 反弹 → 不给弱山寨 LONG）；新增负例"相对强弱例外不得解除 `BENCHMARK_DOWNTREND`"
- BACKLOG：SIG-001（基准冲突阻断/降级）、GRID-006
- 相关：ADR-0006（`blockers` 枚举）
