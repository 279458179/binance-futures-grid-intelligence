# 04｜趋势、突破、扫单与信号引擎

## 多周期职责
- 4H：主趋势、大结构、EMA20/50 与斜率、HH/HL 或 LH/LL、ADX、ATR、显著高低点。
- 1H：回踩/反弹结构、EMA20/50、MACD(12,26,9)、RSI14、ATR14、ADX14。
- 15M：pivot、SFP、MSS/CHOCH/BOS、RVOL、收线与回踩确认。
- 5M：只在高周期方向确认后优化入场，不可单独逆势发信号。

所有指标仅使用已完成 K 线。RVOL 为最近已完成 K 线 quote volume / 前 20 根已完成同周期均量。RSI 超买超卖不是独立反转信号。

## 结构与关键区
4H/1H pivot 左右各至少 2 根收线确认，记录 pivot 真正可用的确认时间，避免未来函数。将相近 swing highs/lows 聚类成价格区域，距离阈值基于 tickSize 与 ATR 参数化。识别前日高低、区间边界、双顶双底、颈线和支撑/压力互换；每个 zone 记录周期、触碰次数、反应幅度和时间。

## 扫单/假突破证据
上扫：价格越过已确认前高/上沿，完成的 15M/1H 收回区域下方；随后跌破相邻 higher-low（bearish MSS）并出现回踩/卖方确认，才可升级 SHORT。下扫反向逻辑：刺破前低后收回上方，再突破 lower-high（bullish MSS）并回踩有效，才可升级 LONG。真突破需收线、成交/主动行为确认及回踩守住。单根影线或瞬时穿越不构成确认。

证据状态：NOT_PRESENT / POSSIBLE / CONFIRMED / FAILED；保存 level、extreme、close、candle_time、structure_break、retest。禁止将推测描述成“主力必然诱多/诱空”。

## 评分与硬闸门
复用现有 `binance-futures-direction-scout` 的 -100..+100 方向评分：4H结构25、1H结构20、15M触发10、MACD8、RSI5、RVOL10、taker flow5、价格+OI+主动成交10、BTC/ETH状态5、相对BTC强弱2。LONG ≥+65、SHORT ≤-65，且4H/1H同向、覆盖率≥80%、无硬闸门。RANGE 独立评分≥70、绝对方向分<40，并要求双边均值回归证据。分数不是概率或胜率。

硬闸门包括：4H/1H严重冲突、基准市场强反向且无相对强势证据、数据过期、流动性不足、异常拥挤/清算冲击、价格远离 EMA20 超过 2×1H ATR、成本无法覆盖目标。任何硬闸门优先于评分。

## 入场状态机
SCANNED → SCORED → WATCH_ONLY；可能状态为 WAIT_BREAKOUT_CLOSE、WAIT_SWEEP_CONFIRMATION、WAIT_PULLBACK、ENTER_ON_CONFIRMATION、NO_TRADE、EXPIRED。触发条件必须机器可判断（收线+回踩+结构+风险闸门），不可只给单一触发价。每次信号保存证据快照和策略版本，LLM 不得修改评分。