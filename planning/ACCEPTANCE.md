# 验收标准与测试矩阵

## 分阶段质量门禁
- Spec Gate：PRD、架构、数据、信号、网格风控、API、部署和 backlog 一致。
- Build Gate：Python/TypeScript lint、format、type-check、unit tests、security scan、容器构建通过。
- Data Gate：合约筛选、采样时间、已收线 K 线、缺失值、429/418 退避测试通过。
- Decision Gate：固定 fixtures 分类一致，无未来函数，无硬闸门绕过。
- Grid Gate：手续费、最小名义金额、止损/损失预算和启动价语义核对。
- Replay Gate：7d/30d 与样本外测试完成，包含成本、滑点、极端行情和数据缺口。
- Cloud Gate：2C2G 压测、TLS/auth、备份恢复、断线和回滚演练完成。

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

## 报告必须字段
as_of UTC、scan_status、BTC/ETH 背景、扫描数量、数据完整性、方向分数及解释、4H/1H/15M、支撑压力区、扫单证据、收线确认状态、signal_trigger、activation_price、entry_zone、grid_lower/upper、格数、成本、仓位可行性、TP/SL、失效条件、有效期、NO_TRADE 原因、回测状态、只读声明。

## 不得宣称完成
- 自动化测试用例存在 ≠ 已用 Binance 实时数据验证。
- 回测脚本可运行 ≠ 已完成样本外盈利验证。
- 有网格提案 ≠ Binance 原生机器人已配置或保证触发。
- 有部署文件 ≠ 云主机已完成 TLS、监控、备份和恢复验收。