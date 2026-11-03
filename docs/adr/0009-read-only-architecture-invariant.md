# ADR-0009｜只读边界是架构不变量，并用负例测试锁死

状态：Accepted
日期：2026-11-03
关联任务：SYS-003、API-001、WEB-004、DEP-002、RND-005

## 背景

AGENTS.md §6、README、docs/01、docs/03、docs/07、docs/08 一致要求：只使用 Binance USDⓈ-M **公共行情**接口，不执行下单/撤单/转账/划转/配置杠杆，不使用交易 API Key；docs/07 明确"无 `POST /orders`"，Grid Planner 页面"只读、不下单"；`contracts/signal-example.json` 有 `orders_placed: false`；docs/09 部署默认 `FUTURES_ONLY_READ_ONLY=true`。

这类约束一旦在实现中破口（例如为了方便加一个"试下单"按钮、或引入带签名的客户端），不是加个开关能收回的——AGENTS.md §6 把它定义为**架构改变，需要单独书面审批与独立隔离流程**。

## 决策

把只读边界做成**可测试的结构性约束**，而不只是配置项：

1. **不存在交易客户端代码路径**：`bfgi/market_data` 只提供公共只读端点的 adapter；不引入任何签名请求（Binance 私有端点需要 `X-MBX-APIKEY` 与 HMAC 签名）。代码里不出现 API key/secret 的配置项——`Settings` 中没有 `BINANCE_API_KEY` 字段，从源头杜绝误用。
2. **端点白名单**：adapter 只允许 docs/03 列出的公共端点（`/fapi/v1/exchangeInfo`、`ticker/24hr`、`klines`、`ticker/bookTicker`、`depth`、`premiumIndex`、`fundingRate`、`openInterest`、`/futures/data/openInterestHist`、`/futures/data/takerlongshortRatio`、`/fapi/v1/symbolAdlRisk`（可选）、`aggTrades`、`time`）。CI 测试扫描 `bfgi/market_data` 与 `apps/*` 源码，出现白名单外的 `/fapi/` 路径或 `X-MBX-APIKEY`、`signature=`、`recvWindow` 等私有参数即失败。
3. **API 负例测试**（API-001）：断言不存在 `POST /orders`、`/cancel`、`/transfer`、`/leverage` 等路由；OpenAPI 里也不出现这些路径；对未知写操作返回 404/405 而不是 500。
4. **前端无下单入口**（WEB-004）：Grid Planner 只提供"复制参数"与"导出 JSON"，测试断言页面源码不含下单/撤单按钮语义；这是"有网格提案 ≠ 已配置交易所机器人"的实现前提。
5. **运行时不变量**：所有决策对象 `orders_placed: false` 恒真。`/api/v1` 下不存在交易类路由，未知写操作路径由兜底中间件记录审计（方法、路径、UTC，不记录 body 与 query 中的敏感值）后返回 404/405——被拒绝的调用也要留痕（对应必测场景 T-22）。
6. 未来若要接入账户/交易能力：本 ADR 被取代（`Superseded by`），需要单独书面审批、独立进程与独立凭据隔离、独立审批流程——不在本项目当前范围内。

## 后果

- 正面：只读性可被 CI 证明；前端与 API 无法在实现中"顺手"加下单入口；没有 API key 配置项就不存在误配风险。
- 负面：不能给"一键下单/半自动执行"这类功能。这是任务书要求，不是缺陷。
- 被否决的备选：提供 `ENABLE_TRADING=false` 开关 + 完整交易客户端代码（存在误启用与凭据风险，且 AGENTS.md §6 要求独立隔离流程）；只在文档里声明只读。

## 关联

- BACKLOG：API-001（合同与权限负例测试）、WEB-004（Grid Planner 只读）、SYS-003、DEP-002
- ACCEPTANCE：Cloud Gate / Build Gate 增加"无交易端点"负例；"不得宣称完成"第 3 条由 `orders_placed: false` 与无下单 UI 保证
- 相关：ADR-0008（措辞禁令）、ADR-0011（审计与失败归因）
