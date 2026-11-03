# 07｜API、前端、提醒与报告规范

> 以下为目标 API 合同，尚未实现。第一期不包含任何委托/下单 API。

## REST API v1
| Method | Path | 功能 |
|---|---|---|
| GET | /healthz | 存活检查 |
| GET | /readyz | DB/worker/数据源就绪 |
| GET | /api/v1/market/summary | BTC/ETH、全市场概览与 freshness |
| POST | /api/v1/scans | 管理员启动受限扫描，异步返回 scan_id |
| GET | /api/v1/scans/{scan_id} | 扫描进度、候选和降级原因 |
| GET | /api/v1/symbols/{symbol}/analysis | 单币结构、指标和证据 |
| GET | /api/v1/candidates?side=LONG | 候选排名，不为凑数放宽规则 |
| POST | /api/v1/grid-plans | 依据已有证据和明确资金输入生成只读方案 |
| GET | /api/v1/grid-plans/{id} | 计划、版本和失效原因 |
| GET/POST | /api/v1/backtests | 查询/启动只读历史回测 |
| GET | /api/v1/alerts | 通知记录 |
| PUT | /api/v1/settings | 管理员更新非秘密策略配置 |

鉴权路径必须 HTTPS，使用 session/JWT 或可信身份代理；管理员动作需 CSRF、速率限制与审计。不得实现 POST /orders、下单、撤单或划转接口。

## 数据合同
信号字段：scan_id、symbol、as_of_utc、valid_until_utc、direction_label、direction_score、range_score、data_coverage、risk_gates、primary_evidence、support_zones、resistance_zones、liquidity_sweep、breakout_confirmation、entry_state、trigger_expression、next_check、risk_notes。

网格提案字段：activation_price、activation_semantics_verified、entry_zone、grid_lower、grid_upper、grid_count、grid_type、fee_assumptions、min_notional_check、TP1、TP2、SL、structural_invalidation、max_loss_if_known、leverage_if_approved、sizing_status、backtest_status。价格使用 Decimal 字符串，例如 "65320.10"。缺失值为 null 并附 data_gaps，不得用零代替。

## UI 页面
- Dashboard：BTC/ETH 多周期环境、全市场状态、LONG/SHORT/RANGE/NO_TRADE 数量、扫描时间和异常。
- Screener：评分、成交额、spread、OI/funding、触发状态、有效期倒计时与数据新鲜度。
- Symbol Detail：4H/1H/15M 图、支撑压力、扫单、成交量/CVD proxy、OI、funding 和风险证据。
- Grid Planner：方向、触发条件、启动价、入场区间、网格上下限/格数、费用、TP/SL、失效和资金预算；仅复制供人工输入。
- Backtest Lab：策略版本、样本区间、成本、MFE/MAE、回撤、样本内外与假设警告。
- Alerts / Settings：观察池、提醒阈值、静默时段、渠道健康、策略配置、备份与系统状态。

## 视觉与通知
专业暗色交易台，桌面与手机响应式；涨跌用文字、图标和颜色冗余表达，不能只靠红绿。评分旁明确说明不是胜率。时间戳始终可见，缺数/过期/失败是明确状态。

事件：NEW_SETUP_WATCH、ENTRY_CONDITION_CONFIRMED、PLAN_INVALIDATED、PLAN_EXPIRED、RISK_ALERT、DATA_DEGRADED。通知必须 event_id 幂等、去重、默认 15M 冷却、有限重试和静默时段；不能把观察机会描述为已下单。