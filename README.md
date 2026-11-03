# Binance Futures Grid Intelligence（永续合约方向网格研判系统）

> 需求基线 / 任务书 v1.0.0（2026-11-03）。当前仓库只有产品规格与开发计划，尚未实现交易系统、尚未部署、尚未回测证明有效。**只做行情研究、策略信号和人工决策支持，不调用真实下单接口。**

## 产品目标
扫描 Binance USDⓈ-M USDT 本位永续合约，针对未来最多四小时的交易决策窗口识别 LONG/SHORT 方向网格候选；稳定双边震荡才考虑 NEUTRAL。输出方向、证据、入场触发条件、入场区间、机器人启动价、网格上下限/格数、止盈止损、失效条件和风险预警。市场不适合必须明确 NO_TRADE，不为了凑数推荐。

“未来四小时”是策略有效期/研判窗口；4H 用于趋势框架，1H 用于结构，15M 用于确认，5M 仅优化入场。没有算法保证方向、盈利或四小时内达标。

## 默认产品与风险边界
- 中文优先，个人自用，桌面与手机响应式。
- 方向性网格优先；高波动不等于中性网格。
- 只读公共行情；禁止自动开仓、撤单、划转、调整保证金；不接入交易权限 API Key。
- 只推荐通过硬风控闸门的候选；不合格时返回观察清单或 NO_TRADE。
- 默认 2–4x；5x 需额外校验；>5x 不生成可执行建议；自动追加保证金关闭。

## 文档导航
| 文件 | 内容 |
|---|---|
| [PRD](docs/01-PRD.md) | 产品需求、用户旅程、功能和非功能目标 |
| [Architecture](docs/02-ARCHITECTURE.md) | 技术栈、模块边界、数据流和存储 |
| [Market Data](docs/03-MARKET-DATA.md) | Binance 数据源、质量、限流和时间对齐 |
| [Signals](docs/04-SIGNALS.md) | 指标、结构、扫单、方向评分和状态机 |
| [Grid & Risk](docs/05-GRID-AND-RISK.md) | LONG/SHORT/NEUTRAL 网格与风险计算 |
| [Backtest](docs/06-BACKTEST.md) | 回测、样本外、纸面模拟与绩效验收 |
| [API & UI](docs/07-API-AND-UI.md) | API 合同、看板、通知与报告 |
| [Security](docs/08-SECURITY.md) | 权限、安全、合规与数据留存 |
| [Deployment](docs/09-DEPLOYMENT.md) | Ubuntu 云主机部署蓝图 |
| [Backlog](planning/BACKLOG.md) | 60 项唯一开发任务 |
| [Acceptance](planning/ACCEPTANCE.md) | 20 个测试场景和阶段门禁 |
| [Milestones](planning/MILESTONES.md) | 版本路线与风险登记 |
| [Signal Example](contracts/signal-example.json) | 虚构测试信号合同 |
| [Agent Rules](AGENTS.md) | Codex/Claude/Agent 开发执行规范 |

## 参考与复用
- [binance-futures-direction-scout](https://github.com/279458179/agent-skills-private/tree/main/skills/binance-futures-direction-scout)：方向评分。
- [binance-grid-decision](https://github.com/279458179/agent-skills-private/tree/main/skills/binance-grid-decision)：网格风险与参数。
- [binance-futures-grid-scout](https://github.com/279458179/agent-skills-private/tree/main/skills/binance-futures-grid-scout)：扫描编排。
- 参考 Binance USDⓈ-M 官方公开 API、Hummingbot、Freqtrade、NautilusTrader、HftBacktest；不直接复制代码，后续核对许可和版本。

## 开发约定
- 只有取得所需实时数据、手续费和风险输入后，方案才可标记 READY_FOR_REVIEW。
- 资金、费率、合约规则/深度、时间戳或历史验证缺失时，返回 PARTIAL/WATCH/NO_TRADE；禁止伪造数据。
- signal_trigger、activation_price、entry_zone 必须区分。
- 限速、缓存、重试和数据过期保护是基础功能。

## 开工顺序
按 [planning/BACKLOG.md](planning/BACKLOG.md) 从 M0 → M1 开始：先完成真实市场数据采集、已收线 K 线校验、无未来函数指标和信号测试，再做网格测算、回测、Web UI 和云部署。所有任务初始 TODO。