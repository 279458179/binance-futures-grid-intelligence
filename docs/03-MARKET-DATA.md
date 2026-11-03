# 03｜市场数据规范与质量合同

## 交易范围
仅扫描 Binance USDⓈ-M 中 `contractType=PERPETUAL`、`quoteAsset=USDT`、`status=TRADING` 的合约。排除稳定币基础资产、杠杆代币、上市不足 30 天或历史不足、流动性异常的标的。

## 数据接口（实现时核对官方字段、权重与窗口）
- `/fapi/v1/exchangeInfo`：合约状态、tickSize、stepSize、minQty、minNotional。
- `/fapi/v1/ticker/24hr`：24h 成交额、涨跌幅、高低价。
- `/fapi/v1/klines`：4h/1h/15m/5m OHLCV、taker buy quote。
- `/fapi/v1/ticker/bookTicker`、`/fapi/v1/depth`：价差与当前盘口深度（不是历史清算热力图）。
- `/fapi/v1/premiumIndex`、`/fapi/v1/fundingRate`：标记价与资金费率。
- `/fapi/v1/openInterest`、`/futures/data/openInterestHist`：当前/历史 OI（历史粒度和可用窗口须实测）。
- `/futures/data/takerlongshortRatio`、`/fapi/v1/aggTrades`：主动买卖代理和可选 CVD 代理。

## 初始筛选阈值（策略配置，可版本化）
24h quote volume ≥ 5,000,000 USDT；spread ≤ 0.15%；±0.5% 深度两侧优选 ≥25,000 USDT。初筛后 60–100 个标的做多周期计算，精选 20–30 个请求较贵的 OI/主动成交/深度数据。阈值必须回测校准，不是交易所事实。

## 时间和质量
所有时间使用 UTC，内部毫秒时间戳。仅使用已完成 K 线；通过交易所 server time 校准时钟。ticker/book 建议新鲜度 ≤30 秒；OI/funding 按接口更新周期标注。每个数据族独立记录 provider 时间、采集时间、覆盖率和质量。必需数据覆盖率低于 80%、K 线缺口、盘口倒挂或 bid/ask 非正时，降级为 PARTIAL/STALE/NO_TRADE，不得回填陈旧价格。

## 指标解释
OI 增加只表示未平仓量变化，不说明主动开多或开空；须结合价格和主动成交。CVD_proxy 可用 `Σ(2*taker_buy_quote-total_quote_volume)`，必须标注数据源、周期与覆盖，不等于全市场真实 CVD。资金费率是拥挤与持仓成本背景，不能单独预测方向。公开 REST depth 是当前盘口快照，不是清算热力图。

## 限流与合规
429 按 Retry-After/权重头退避；418 停止请求并报告限制，禁止换 IP 绕过；5xx 有限重试并断路。保存原始快照 7–30 天可配置，策略与 K 线数据独立留存用于回放。部署地区必须遵守当地法律与交易所条款。