# ADR-0005｜开发期以冻结 fixtures 为验证基准；Binance HTTP 451 走降级路径，不绕过

状态：Accepted
日期：2026-11-03
关联任务：DATA-001..DATA-007、SIG-006、SYS-004

## 背景

开发机访问 `https://fapi.binance.com/fapi/v1/time` 返回 **HTTP 451**：`{"code":0,"msg":"Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms…"}`。项目规则一致禁止绕过：

- README / docs/01：只读公共行情，不做交易能力；
- docs/02 §6：**禁止跨区域/身份轮换绕限制**；
- AGENTS.md §8：工具不可用要如实标记 `NOT_VERIFIED`，不得假报成功。

如果因此暂停实现，60 个任务里所有 DATA/IND/STR/SIG/GRID/BT 都被一个环境限制阻塞；而契约、校验、指标、评分、闸门、网格计算、回测**都可以用离线数据完整验证**。

## 决策

1. **实现按公开 REST 契约写**：endpoint、参数、返回字段、错误码、权重头，全部照 docs/03 文档化契约实现，不猜测、不自定义响应形状。
2. **验证基准是冻结 fixtures**：`tests/fixtures/binance/` 保存真实响应结构的样例（exchangeInfo、ticker/24hr、klines、depth、premiumIndex、openInterestHist、takerlongshortRatio 等），带 `captured_at`、来源标注与不可变 hash。回归集（SIG-006）≥14 个案例，覆盖 golden cases。
3. **451/地理受限本身是一条真实的降级路径**：客户端必须把它分类为可诊断的 provider 错误，产出 `PARTIAL`/`STALE`/`DATA_DEGRADED`（docs/03、docs/07 的 `data_gaps`），而不是崩溃、也不是重试打爆。
4. `BINANCE_FUTURES_API_BASE` 保持可配置——这是正常配置项，不是绕过手段；不由代码自动切换到任何规避性端点或代理池。
5. **凡是需要真实市场数据才能确认的部分（真实权重、真实限速、真实字段漂移、实盘可用性）在交付报告与 `planning/ACCEPTANCE.md` 状态里标 `NOT_VERIFIED`**，写清原因（地理限制）与风险。
6. 网络层测试用本地 HTTP mock（ASGI/httpx MockTransport）复现 429/418/451/5xx/超时/断连，不允许真实打交易所（DATA-005）。

## 后果

- 正面：M0/M1/M2 全部可在离线环境真正跑通并测试；上线前只要换一台可访问的机器或等地理条件变化即可做真实校验，代码不变。
- 负面：字段级别的真实漂移（Binance 改字段/精度）只有真实访问才能发现。缓解：客户端对未知字段宽松解析 + 对必需字段严格校验，并在契约测试中固定必需字段清单。
- 被否决的备选：代理/换区/换身份访问（明确禁止）；暂停实现直到能访问（把环境限制变成项目阻塞）。

## 参考判断（jev，模型判断，非已验证事实）

`mcp__jev_judgment__judge`（jev-1.14.0）noul = 0.92：以冻结 fixtures 实现 + 如实标注 `NOT_VERIFIED` + 绝不绕过，是正确工程响应。

## 关联

- BACKLOG：DATA-001（fixtures + 断线测试）、DATA-005（429/418 可复现且不绕限流）、SIG-006（≥14 案例回归集）
- ACCEPTANCE：真实市场验证项在验收表中标 `NOT_VERIFIED` 并注明原因
- 被否决的备选：任何地理/身份绕过；暂停项目
