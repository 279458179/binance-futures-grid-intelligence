# 06｜回测、模拟与证据有效性

## 原则
所有规则先验证再用于人工决策。冻结策略版本、指标参数、费用假设和可交易时间；禁止未来函数。一次好看的行情或短期样本不能证明策略有效。

## 数据覆盖
初始标的 BTCUSDT、ETHUSDT、SOLUSDT、BNBUSDT、DOGEUSDT，随后扩展到不同流动性和市场状态。覆盖上涨、下跌、横盘、波动率爆发、资金费率/清算冲击和流动性异常。7d/30d 是开发验收起点，不足以证明稳健；后续必须更长周期、walk-forward 和样本外测试，并记录上市/退市幸存者偏差。缺少历史 OI/taker 数据时需明确降级。

## 防未来函数
时间 T 只能使用 close_time≤T 且当时已可获取的数据。pivot 只有右侧 K 线完成后才成立；15M 突破/扫单在收线后才确认。模拟成交不能假设刚好以 K 线高低点成交。保存 source timestamps，保证实时与历史回放一致。不得全样本调参后又称同一数据为样本外。

## 三层验证
1. 信号回放：统计后续 4h 方向结果、MFE、MAE、触发率、假突破确认和失效原因；未触发信号不算盈利交易。
2. 网格撮合仿真：模拟逐级订单、库存、止损、手续费、资金费率、滑点与延迟。OHLCV 无法判定同根 K 线先高后低，采用最不利路径或细粒度数据并标注不确定性。
3. Paper tracking：跨多个市场 regime 比较计划价与可成交价、滑点、通知延迟、数据缺口、重复信号、虚拟仓位 PnL。

## 指标与版本
报告 net_pnl、net_return、max_drawdown、profit_factor、win_rate、expectancy、turnover、fee_drag、funding_drag、MFE/MAE、trade_count、trigger_rate；LONG/SHORT/NEUTRAL 分开统计，提供置信区间/样本量。比较不交易、EMA顺势、突破回踩、固定方向网格等基线。每次回测绑定 git_commit、strategy_version、market_data_hash、参数、费率与滑点假设。

## 失败条件
若样本外收益差、样本数不足、成本/成交假设无法验证或最小名义额不明确，标记 NOT_VALIDATED，不得输出 READY_FOR_REVIEW 或声称可盈利。