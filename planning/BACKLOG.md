# 全量开发任务清单（唯一任务基线）

> 共 60 项，全部初始状态 TODO。每项有唯一 ID、优先级、依赖和验收交付物。正式开发以此生成 GitHub Issues/Project 看板；变更业务行为须同步更新 PRD、测试与任务清单。

## M0｜独立仓库、工程规范与数据底座（P0）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| SYS-001 | 独立仓库、README、规范 | 无 | main、任务书和权限策略可核验 |
| SYS-002 | Python Monorepo / Backend / Worker / TS Web | SYS-001 | 包结构、依赖锁定、本地一键安装 |
| SYS-003 | CI：lint/format/typecheck/unit/secret scan | SYS-002 | PR 自动执行，失败拒绝合并 |
| SYS-004 | UTC、Decimal、schema、错误码 | SYS-002 | 价格/时间单测和 schema 版本化 |
| SYS-005 | Docker 开发环境与变量模板 | SYS-002 | 无 secrets 的 compose config 成功 |
| DATA-001 | Binance 公共 API、exchangeInfo、24h ticker | SYS-004 | 全市场合约列表、fixtures、断线测试 |
| DATA-002 | 4H/1H/15M/5M K 线采集与历史分页 | DATA-001 | 已收线、缺口和重复检查 |
| DATA-003 | 可选 WebSocket ticker + REST 兜底 | DATA-001 | 断线重连、时间戳标记 |
| DATA-004 | OI/taker/funding/depth/mark price | DATA-001 | 来源、UTC 时间、N/A 和限流测试 |
| DATA-005 | 权重预算、限流队列、退避、缓存、熔断 | DATA-001 | 429/418 可复现且不绕限流 |
| DATA-006 | PERPETUAL/USDT/TRADING/量/价差/深度过滤 | DATA-001/004 | 非标、冷门、异常盘口拒绝 |
| DATA-007 | SQLite WAL、migration、快照谱系 | SYS-004 | 报告可追溯，迁移/回滚演练 |

## M1｜可重放多周期方向与扫单引擎（P0）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| IND-001 | EMA/MACD/RSI/ATR/ADX/RVOL | DATA-002 | 参考值一致，仅用收线 K |
| IND-002 | taker flow、CVD proxy、OI/funding 上下文 | DATA-004 | 不误判 OI 方向，缺数不给分 |
| STR-001 | 4H/1H swing/pivot 与 S/R 聚类 | IND-001 | 无未来函数、区域可解释 |
| STR-002 | 前高低、双顶底、颈线、区间边界 | STR-001 | fixtures 识别准确 |
| STR-003 | BSL/SSL、扫单/SFP、假/真突破 | STR-001/002 | 极值、收线、MSS、回踩证据齐全 |
| STR-004 | BOS/MSS/CHOCH 与 15M 状态机 | STR-003 | 仅插针不确认信号 |
| SIG-001 | BTC/ETH Regime、相对 BTC 强弱 | IND-001 | 基准冲突阻断/降级 |
| SIG-002 | 方向 -100..100、区间 0..100 评分 | SIG-001/IND-002/STR-004 | 逐项证据可追溯 |
| SIG-003 | 流动性/风险/数据硬闸门与 NO_TRADE | SIG-002 | 硬拒绝优先于高分 |
| SIG-004 | 全市场扫描协调、候选排名、单币分析 | DATA-005/SIG-003 | 数量准确、可中断、仅收线 |
| SIG-005 | 4h 有效期、失效状态、下次观察条件 | STR-004/SIG-004 | 旧方案自动 STALE/EXPIRED |
| SIG-006 | 冻结历史 fixtures 回归集（≥14 案例） | SIG-003/005 | 正反、缺数、冲击和流动性场景覆盖 |

## M2｜方向网格策略、风险和回测（P1）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| GRID-001 | LONG/SHORT/NEUTRAL/NO_TRADE 路由 | SIG-003 | 单边高波动不进中性 |
| GRID-002 | 结构+ATR 构建上下限/入场区间 | STR-002/GRID-001 | 边界有来源、过期校验 |
| GRID-003 | 分离 signal_trigger/activation_price/entry_zone | GRID-002 | 原生 Bot 语义经核验 |
| GRID-004 | 几何/等差格数、每格毛/净间距 | GRID-002/DATA-004 | 高成本/不足间距拒绝 |
| GRID-005 | 交易规则、步长、minNotional、保证金 | GRID-004 | 余额缺失输出 PARTIAL |
| GRID-006 | TP1/TP2、SL、结构失效、RR、日亏上限 | GRID-002/005 | 风险预算内且止损可实施 |
| GRID-007 | 相关敞口、funding、ADL、波动挤压闸门 | GRID-006 | 风险失败不得 READY |
| BT-001 | 历史数据提取、fixture 清洗、幸存者偏差 | DATA-007 | 数据质量报告和 hash |
| BT-002 | 事件驱动逐根无未来函数回放 | BT-001/SIG-006 | 实时与回放输出一致 |
| BT-003 | 网格订单/库存/手续费/funding/滑点仿真 | BT-002/GRID-007 | 双触发路径保守处理 |
| BT-004 | 7/30 天及更长 walk-forward 样本外 | BT-003 | 版本化报告和缺数记录 |
| BT-005 | 基准对照与绩效报表 | BT-004 | 净 PnL、MFE/MAE、MaxDD 等 |
| BT-006 | 只读 paper tracking | BT-005 | 跨 regime 跟踪，不发真实单 |

## M3｜Web/API/监控产品化（P2）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| API-001 | FastAPI OpenAPI/schema/auth/error | SYS-004/SIG-004 | 合同及权限负例测试 |
| API-002 | 扫描/候选/分析/计划/回测 API | API-001/GRID-007 | 时间/来源/过期标记可复算 |
| WEB-001 | 响应式暗色 UI Shell | SYS-002 | 桌面/手机层级清晰 |
| WEB-002 | 市场总览、筛选排序、freshness | WEB-001/API-002 | 无数据/失败/空结果状态完整 |
| WEB-003 | K 线及 S/R/扫单/突破标注 | WEB-002/STR-003 | 可关联原始 K 线和 signal ID |
| WEB-004 | 网格参数/复制/风险审查卡 | WEB-002/GRID-007 | 无下单按钮 |
| WEB-005 | 回测中心、PnL 分解、策略比较 | WEB-002/BT-005 | 区分样本内外 |
| OPS-001 | 15M 扫描、单 Worker 锁、退避 | SIG-005 | 无重复任务，重启可恢复 |
| OPS-002 | watchlist、有状态提醒、冷却去重 | OPS-001 | 同一事件一次通知 |
| OPS-003 | Telegram/邮箱/飞书通知适配 | OPS-002 | 凭据安全、失败重试 |
| OPS-004 | 健康端点、metrics、结构化日志 | API-001/OPS-001 | scan_id 可定位，日志脱敏 |

## M4｜云部署、验收与运营（P2）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| DEP-001 | Dockerfile、多阶段构建、镜像扫描 | M3 核心 | 非 root、镜像固定 |
| DEP-002 | Compose/反代/HTTPS/内网数据层 | DEP-001 | 仅公网 443/授权 SSH |
| DEP-003 | SQLite→Postgres 迁移接口与备份 | DATA-007/DEP-002 | 迁移与恢复不丢数据 |
| DEP-004 | Ubuntu 24.04 安装脚本和 Runbook | DEP-002 | 新机器可重复安装 |
| DEP-005 | 2C2G 压测与 48h 稳定性 | DEP-004 | 资源瓶颈有实测结论 |
| DEP-006 | 断网/重启/DB 损坏/限流/回滚演练 | DEP-004 | 故障恢复有证据 |
| DEP-007 | 最终 UAT 全流程验收 | M0–M4 | PRD/测试/运行日志可追溯 |

## M5｜进阶研究（P3，非 MVP 阻塞）
| ID | 任务 | 依赖 | 完成标准 |
|---|---|---|---|
| RND-001 | 第三方强平热力图插件化接入 | DATA-004 | 许可/来源明确，失败可降级 |
| RND-002 | WebSocket 订单流与细粒度 CVD | DATA-003 | 可重放、延迟/丢包可解释 |
| RND-003 | HftBacktest/NautilusTrader 撮合验证 | BT-003 | L2 数据与费用模型可审计 |
| RND-004 | Freqtrade/Hummingbot 策略对照 | BT-005 | 同标的/时间/成本基准 |
| RND-005 | LLM 解释适配器（非决策核心） | API-002 | 模型断开不影响计算，引用证据 ID |

## GitHub Issue 规范
标题格式 `[P0][DATA-002] Implement closed-candle klines ingestion`。每个 Issue 必须写目标、输入/输出 schema、依赖、异常与负例、自动测试、验收证据、风险/回滚和变更边界。一个 PR 原则上完成一个任务或紧密依赖闭包；未测试不得标 Done。