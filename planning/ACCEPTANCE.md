# 验收标准与测试矩阵

## 分阶段质量门禁
- Spec Gate：PRD、架构、数据、信号、网格风控、API、部署和 backlog 一致。
- Build Gate：Python/TypeScript lint、format、type-check、unit tests、security scan、容器构建通过。
- Data Gate：合约筛选、采样时间、已收线 K 线、缺失值、429/418 退避测试通过。
- Decision Gate：固定 fixtures 分类一致，无未来函数，无硬闸门绕过。
- Grid Gate：手续费、最小名义金额、止损/损失预算和启动价语义核对。
- Replay Gate：7d/30d 与样本外测试完成，包含成本、滑点、极端行情和数据缺口。
- Cloud Gate：2C2G 压测、TLS/auth、备份恢复、断线和回滚演练完成。

## 由 ADR 追加的门禁项

以下条目来自 `docs/adr/`（AGENTS.md §10：遇到需求冲突先更新任务书与验收标准），与上面的 Gate 同等强制：

| 门禁项 | 来源 | 断言方式 |
|---|---|---|
| 决策/方向/入场/置信度/阻断码/数据缺口枚举一致性 | ADR-0006 | `bfgi/core/enums.py` 单一来源；契约测试同时覆盖合法组合与非法组合（LOW 不得给方向、`GRID_PLAN` 需 ≥MEDIUM） |
| 无交易能力负例 | ADR-0009 | API 不存在 `/orders`、`/cancel`、`/transfer`、`/leverage`；源码扫描无 `X-MBX-APIKEY`/签名参数/白名单外 `/fapi/` 路径；`Settings` 无 API key 字段；Grid Planner 无下单入口 |
| 禁用措辞扫描 | ADR-0008 | 报告模板渲染输出与前端文案常量必须通过 `assert_no_banned_phrasing`；置信度数值必须与等级、硬闸门结果和"不是胜率"标签同时出现 |
| 基准耦合守卫并集 | ADR-0007 | 新增负例 T-21：相对强弱例外不得解除 `BENCHMARK_DOWNTREND`/`BENCHMARK_UPTREND` |
| 模块依赖方向 | ADR-0001 | CI AST import 约束测试：`indicators/structure/scoring/grid_planner/risk/backtest` 不得 import 网络层或 persistence |
| migration 回退与备份恢复演练有证据 | ADR-0010 | `schema_migrations` 版本化、up/down 成对、演练脚本输出留档 |
| 版本身份与失败归因字段必填 | ADR-0011 | 决策/计划/回测记录必须含 `strategy_version`、`git_commit`、`market_data_hash`；`plan_revisions.primary_cause` 属固定 8 值枚举 |
| 真实市场数据验证的如实标注 | ADR-0005 | 见下方"当前验证状态"，缺证据的项写 `NOT_VERIFIED` 而非通过 |

## 必测场景
| ID | 场景 | 期望结果 |
|---|---|---|
| T-01 | 4H/1H 上涨一致，15M 下扫收复 + MSS | 确认前 WAIT，确认后才可能 LONG_GRID |
| T-02 | 4H/1H 下跌一致，15M 上扫收回 + MSS | 确认前 WAIT，确认后才可能 SHORT_GRID |
| T-03 | 仅长上影，无结构变化 | 不直接 SHORT_GRID |
| T-04 | 仅长下影，收盘未收回 | 不直接 LONG_GRID |
| T-05 | 突破放量但未回踩、远离 EMA20 | WAIT_PULLBACK，不追价 |
| T-06 | EMA 金叉但 4H/1H 看跌 | NO_TRADE |
| T-07 | 双侧区间反复成交、ADX 低、ATR 稳定 | 只有通过独立风控才可能 NEUTRAL_GRID |
| T-08 | 突破伴 ATR 扩张、OI/清算冲击 | WAIT/NO_TRADE，禁止 NEUTRAL_GRID |
| T-09 | BTC/ETH 强空，山寨仅 15M 反弹 | 不给弱山寨 LONG |
| T-10 | funding 极端拥挤、OI 涨价滞涨 | 拒绝同向拥挤网格 |
| T-11 | 缺一根应收 15M K 线 | STALE/NO_TRADE，不借旧值 |
| T-12 | 成交额不足或 bid/ask 错误 | 不进入优选 |
| T-13 | 手续费+滑点高于单格毛收益 | NO_TRADE |
| T-14 | 保证金/费率/合约规则未知 | PARTIAL，不给精确订单量 |
| T-15 | 用户输入 120x | 拒绝可执行提案 |
| T-16 | 未启动且价格偏离快照 >1×15M ATR | EXPIRED/STALE，要求重算 |
| T-17 | WS 断线、REST 失败 | 旧值标 STALE，发 DATA_DEGRADED |
| T-18 | Worker 重启后重复扫描同一 15M 窗口 | 不重复发送同一事件 |
| T-19 | 回测在 candle close 前读取 pivot 右侧数据 | 测试失败，阻止未来函数 |
| T-20 | 网格已实现利润正、方向库存亏损 | 总损益计入未实现亏损 |
| T-21 | 山寨跑赢 BTC ≥1.0pp（4h 与 24h），但 BTC/ETH 同时命中定量耦合守卫 | 基准项可得分，仍不给 `GRID_PLAN`；`blockers` 含 `BENCHMARK_DOWNTREND` |
| T-22 | 请求带交易意图（下单/撤单/改杠杆） | 无对应端点，返回 404/405 并留审计记录，不产生任何交易调用 |

## 报告必须字段
as_of UTC、scan_status、BTC/ETH 背景、扫描数量、数据完整性、方向分数及解释、4H/1H/15M、支撑压力区、扫单证据、收线确认状态、signal_trigger、activation_price、entry_zone、grid_lower/upper、格数、成本、仓位可行性、TP/SL、失效条件、有效期、NO_TRADE 原因、回测状态、只读声明。

## 不得宣称完成
- 自动化测试用例存在 ≠ 已用 Binance 实时数据验证。
- 回测脚本可运行 ≠ 已完成样本外盈利验证。
- 有网格提案 ≠ Binance 原生机器人已配置或保证触发。
- 有部署文件 ≠ 云主机已完成 TLS、监控、备份和恢复验收。

## 当前验证状态（截至 2026-11-03，随实现更新）

| 项目 | 状态 | 原因 / 条件 |
|---|---|---|
| Binance 公共 API 可达性、真实权重与限速、字段漂移 | `NOT_VERIFIED` | 开发机访问 `fapi.binance.com` 返回 HTTP 451（地区受限）。按 ADR-0005 不绕过；需可在目标网络访问公共 API 的环境 |
| 真实合约 universe 与流动性阈值命中情况 | `NOT_VERIFIED` | 依赖 `exchangeInfo`/`ticker/24hr` 真实响应；离线只验证筛选逻辑本身 |
| 7d/30d 回测与样本外指标 | `NOT_RUN` | 需要冻结的 klines fixtures 或真实历史数据；先跑 fixture 版本，真实数据版本另标 |
| 2C2G 压测、TLS/auth、备份恢复、断线与回滚演练 | `NOT_VERIFIED` | 需要真实 Ubuntu 24.04 主机；仓库内提供脚本与演练步骤，实际演练结果留档后才可标通过 |
| `activation_price` 语义是否与所选机器人实现一致 | `NOT_VERIFIED` → `activation_semantics_verified: false` | 交易所机器人语义需真实核对，未核对前不得给出可执行触发承诺 |