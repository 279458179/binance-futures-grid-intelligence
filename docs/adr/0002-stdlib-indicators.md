# ADR-0002｜指标内核用纯 Python 标准库，不引入 numpy/pandas/TA-Lib

状态：Accepted
日期：2026-11-03
关联任务：IND-001、IND-002、SYS-002

## 背景

`docs/02-ARCHITECTURE.md` §2 把 `numpy/pandas` 标为"建议"、TA-Lib 标为"可选"。三条约束同时生效：

1. AGENTS.md §6 / docs/02 §6：指标必须是确定性、可重放、无未来函数的纯计算；"实时与回放输出一致"是验收项（BT-002）。
2. AGENTS.md §11：目标环境 Ubuntu 24.04、普通 CPU、2C2G 级别，核心扫描不依赖 GPU。TA-Lib 是 C 扩展，在 Windows/容器上的安装与 ABI 问题是长期维护负担。
3. 计算量很小：deep 集最多 30 个 symbol（`MAX_DERIVATIVES_SYMBOLS=30`），每个 4h/1h/15m/5m 各 100–300 根 K 线，指标是 O(n) 滑动窗口，总规模在 10^4 数量级——远不到需要向量化加速的量级。

同时 docs/02 §7 要求价格用 Decimal 或字符串序列化，float 只能是中间值且**不得决定 tick/数量合规**。pandas 的 float64 列会让"哪个数字参与合规判定"变得不可审计。

## 决策

- 指标内核（EMA、SMA、RSI14、ATR14、ADX14、Bollinger 带宽、RVOL、摆动点、CVD_proxy、OI 变化）用纯 Python 实现，输入是 `Candle` 序列，价格路径用 `Decimal`，需要连续近似时（RSI/ADX 的 Wilder 平滑）用 `float` 但在类型上明确标记为"评分用近似值"，不进入价格/数量合规判定。
- 每个指标带显式窗口语义：只允许使用 `close_time <= as_of` 的已收线（IND-001），并提供 `warming_bars` 与"数据不足 → N/A"返回值，禁止静默补齐。
- 数值容差写进单元测试：断言用 `abs(a-b) <= 1e-9` 这类显式容差，禁止用"跑通就算对"。
- 若将来某层真的成为瓶颈，允许在保持接口与测试不变的前提下替换实现（先做基准，再改）。

## 后果

- 正面：依赖面最小（Python 侧只有 FastAPI/httpx/pydantic 等 I/O 依赖），确定性可测，跨平台安装简单，无 C 扩展；指标单元测试可以精确到小数位。
- 负面：没有 pandas 的便利性；扫描性能靠缓存与限量（docs/02 §6 的并发上限与 symbol 上限）而不是靠向量化。风险有限：30 symbol × 4 周期 × ~300 bar 在纯 Python 下是毫秒级。
- 被否决的备选：TA-Lib（C 扩展、安装/ABI 风险、难以精确定义 warmup 与 NaN 语义）；numpy/pandas（此处无性能收益，且 float64 与 Decimal 规则冲突）。

## 参考判断（jev，模型判断，非已验证事实）

`mcp__jev_judgment__judge`（jev-1.14.0）两次独立提问：`pure_stdlib` 0.79（confidence 0.68）与 0.97（confidence 0.96）。两次一致。作为选型参考输入，最终结论仍基于本项目的确定性与 2C2G 约束。

## 关联

- BACKLOG：IND-001（无未来函数）、IND-002（指标单元测试覆盖边界）
- ACCEPTANCE：指标测试覆盖空/单根/全同价/缺口/不足窗口
- 被否决的备选：TA-Lib、numpy/pandas 内核
