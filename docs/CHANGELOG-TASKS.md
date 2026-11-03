# 任务变更记录（AGENTS.md §10）

每个合并/提交按 Task ID 记录：改变了什么 API/策略、测试证据、风险、迁移与回滚、已知缺口。倒序排列。

---

## 2026-11-03｜前置：ADR 决策集（无 Task ID，属开工前置）

**改变了什么**
- 新增 `docs/adr/` 共 12 份 ADR + 索引（见 `docs/adr/README.md`），覆盖包结构、指标内核、调度、前端、离线验证、决策词汇、基准闸门、措辞禁令、只读边界、持久化、版本身份与失败归因。
- `planning/ACCEPTANCE.md`：新增"由 ADR 追加的门禁项"表、必测场景 T-21/T-22、"当前验证状态"表。
- 无代码变更、无 API 变更、无数据变更。

**测试**
- 无自动化测试（本提交只改文档）。验收影响：ADR 追加的门禁项将在对应 Task 实现时以测试形式落地（SYS-003/SYS-004、API-001、WEB-004、DATA-007、BT-006）。

**风险**
- ADR-0004 偏离 docs/02 的 Next.js 主选（理由：docs/09 的 2GB VPS 构建内存警告 + 无 SEO/SSR 需求）。若你要求严格按 docs/02 主选，需 Supersede ADR-0004 并改 `apps/web`。
- ADR-0003 保留 APScheduler（docs/02 建议），幂等靠 DB 约束；jev 在此项上判断不稳定，未作为依据，属可复核决策。
- ADR-0007 取更严格一侧 → 机会减少、`WATCH/NO_TRADE` 增多。

**迁移 / 回滚**
- 纯文档新增，回滚即 `git revert` 该提交，无数据迁移。

**已知缺口**
- Binance 公共 API 返回 HTTP 451（地区受限）→ 真实市场验证项已在 ACCEPTANCE 标 `NOT_VERIFIED`（ADR-0005）。
- 仓库尚无 CI workflow（SYS-003 待实现），ADR 声称的 CI 门禁目前只是待落地的要求。

**诚实记录**
- 本会话中我曾生成过一份 `docs/adr/0003-asyncio-scheduler-db-lease.md` 草稿，随后因决策反转（改为保留 APScheduler）删除了它，并重写为 `0003-scheduler-and-slot-lease.md`。该文件是我自己几分钟前创建的未提交草稿，未包含你的任何内容，也从未被提交；删除只影响我自己的草稿，且编号未复用。
