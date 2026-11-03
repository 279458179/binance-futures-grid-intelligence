# ADR-0008｜分数不是概率：措辞禁令与可执行的输出校验

状态：Accepted
日期：2026-11-03
关联任务：SIG-004、GRID-001、WEB-001..WEB-005、RND-001..RND-005、SYS-003

## 背景

任务书与三套参考 skill 反复要求同一件事，但方式不同：

- docs/04 / direction-scout：方向分 −100..+100、区间分 0..100，**两者都不是概率**；不得表述为胜率。
- grid-decision：禁止"稳赚/必赚/稳稳赚钱"；不得把短期回测年化外推为可靠收益。
- grid-scout：禁止"必涨/必跌/稳赚/高胜率"；未核验项写 `NOT_VERIFIED`。
- docs/09：每个输出必须带"仅作研究和辅助决策，不保证收益，不自动下单"。
- AGENTS.md §5：禁止 fabricated price / exact liquidation / win probability / backtest（未真实完成时）。

`contracts/signal-example.json` 已经有 `score_is_probability: false`。风险在于：LLM 生成的中文解读、前端文案、报告模板是最容易把这些禁令写漏的地方，而 AGENTS.md §4 又要求 LLM 只能解释、不能改信号。

## 决策

1. **契约层**：所有决策/网格输出对象固定携带 `score_is_probability: false` 与 `confidence_is_probability: false`（见 ADR-0006），并在 OpenAPI 描述中写明"评分是相对倾向强度，不是概率"。
2. **禁止措辞清单**落进代码，而不是只写在文档里：`bfgi/reporting/banned_phrases.py` 维护禁用词表（至少：必涨、必跌、稳赚、必赚、稳稳赚钱、保证收益、高胜率、胜率、无风险、稳赢、必然、liquidation 精确价位断言），并提供 `assert_no_banned_phrasing(text)`。
3. **测试强制**（SYS-003 CI 门禁之一）：
   - 报告模板渲染测试：对每套模板用固定 fixtures 渲染，输出必须通过 `assert_no_banned_phrasing`。
   - 前端文案静态检查：`apps/web` 的文案常量同样过一遍禁用词扫描（测试文件里读取源码常量，不需要浏览器）。
   - UI 层：置信度数值必须与 `confidence` 等级、`blockers` 列表和"不是胜率"标签同时出现（ADR-0006），WEB 测试断言标签存在。
4. **LLM 只用于解释**（RND 层，可插拔、默认关闭）：解读文本必须经过同一条 `assert_no_banned_phrasing` 与"不得新增数字"检查（不得引入决策对象中不存在的价位、数量、收益率）；检查失败则丢弃该文本，只保留确定性字段渲染。默认路径不依赖 LLM（AGENTS.md §11）。
5. **不产出精确爆仓价 / 强平距离**：资金与仓位未知时 `max_loss_usdt: null` + `sizing_status: PARTIAL/NOT_CALCULATED`，只给市场可推导的区间与公式说明（docs/05、T-14）。
6. **回测未真实完成不得写"回测通过"**：`backtest.days_7/days_30` 只允许 `NOT_RUN | NOT_VALIDATED | COMPLETED`（docs/06），前端与 API 原样透传，不美化。

## 后果

- 正面：禁令从"文档要求"变成"CI 会红的测试"，避免实现过程中靠人记住措辞；LLM 参与时被关在解释层。
- 负面：禁用词表可能误伤合法用语（例如"胜率"出现在引用外部资料时）。缓解：词表按上下文位置分级——决策/报告/UI 输出严格禁止，注释与文档引用不受该测试约束。
- 被否决的备选：只在 docs 里写禁令（不可验证）；把置信度改叫"胜率"（直接违反任务书）。

## 参考判断（jev，模型判断，非已验证事实）

noul 0.88：置信度数值在 UI 中必须与"不是概率/不是胜率"标签及等级、硬闸门结果共同呈现，而非裸百分比。

## 关联

- BACKLOG：SYS-003（CI 门禁）、SIG-004、RND-001（LLM 解读边界）
- ACCEPTANCE：Build Gate 增加"禁用措辞扫描"；报告必须字段中的"只读声明"由测试保证
- 相关：ADR-0006、ADR-0009
