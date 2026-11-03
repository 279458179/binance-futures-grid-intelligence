# ADR-0011｜版本身份、数据血缘与失败归因分类是每条结论的必填字段

状态：Accepted
日期：2026-11-03
关联任务：SYS-004、BT-006、GRID-007、OPS-003、DEP-007、API-002

## 背景

- docs/06：每次回测必须绑定 `git_commit`、`strategy_version`、`market_data_hash`、参数、费用/滑点假设；失败时结果写 `NOT_VALIDATED`，不得写 `READY_FOR_REVIEW`。
- docs/09：每个计划修订都要版本化，并记录规则版本与数据 hash；发布需要可审查的 commit SHA、镜像 digest、配置样例、诊断/备份/恢复与回滚证据。
- grid-decision 参考：失败归因必须先记录**一个主要原因**，才允许改参数，分类为 `REGIME_ERROR | BAND_ERROR | GRID_DENSITY_ERROR | LEVERAGE_ERROR | CAPITAL_FEASIBILITY_ERROR | EXECUTION_ERROR | DISCIPLINE_ERROR | EXTERNAL_SHOCK`。
- AGENTS.md §10：每次合并记录 Task ID、改变的 API/策略、测试、风险、迁移/回滚、已知缺口。

风险：没有版本身份，"这条建议当时用哪套规则、哪些数据算出来的"无法复现；没有失败归因，参数会被反复乱调（用改参数掩盖判断错误）。

## 决策

1. **版本身份三元组**，在任何持久化记录与 API 响应里必填：
   - `strategy_version`：策略/规则版本，取自语义化版本常量（`bfgi/core/version.py`），与 scoring/grid 规则变更同步递增（规则变更必须同时有 ADR 或 BACKLOG 更新，见 ADR-0000）。
   - `git_commit`：构建时注入（镜像 build arg / 启动时读取 `.git`），不硬编码。
   - `market_data_hash`：本次扫描使用的关键输入集合的 SHA-256（fixture 场景用 fixture 集 hash），保证同一输入可复现同一结论。
   另加 `schema_version`（契约版本，ADR-0006）与 `image_digest`（发布物，DEP-007）。
2. **血缘链**：`scan_runs → decisions → grid_plans → plan_revisions → alerts / backtest_runs`，每一跳都带上述三元组与 `snapshot_at_utc`；报告与 UI 必须展示 `strategy_version` 与 `snapshot_at_utc`（ACCEPTANCE 报告必须字段）。
3. **失败归因**：`plan_revisions.primary_cause` 与 `system_audit.primary_cause` 使用上面的固定 8 值枚举；只允许一个 primary cause，其他因素进 `contributing_causes[]`。规则：先归因、再改参数；没有 primary cause 的参数改动测试必须拒绝（防止"改参数掩盖判断错误"）。
4. **回测状态**：`NOT_RUN | NOT_VALIDATED | COMPLETED`，只有 `COMPLETED` 才允许引用其指标；`COMPLETED` 还要求样本外窗口与数据缺口披露齐全（docs/06）。
5. **变更留痕**：`docs/CHANGELOG-TASKS.md` 按 Task ID 记录每次合并的：Task ID、改变的 API/策略、测试证据、风险、迁移/回滚、已知缺口（AGENTS.md §10 的落地载体）。

## 后果

- 正面：任何一条 UI 上看到的建议都能回溯到当时的规则版本与输入数据；失败分析有强制结构，参数调整有前置条件；发布可审计。
- 负面：字段变多，样例 fixtures 与契约测试要一起维护；`market_data_hash` 需要定义稳定的规范化方式（排序 + 关键字段子集），否则同一数据不同序列化会产生不同 hash。缓解：规范化函数放在 `bfgi/core/hashing.py` 并有单元测试。
- 被否决的备选：只记 `strategy_version`（无法定位当时输入）；把失败归因做成自由文本（无法统计与回归）。

## 关联

- BACKLOG：SYS-004、BT-006、GRID-007、OPS-003、DEP-007
- ACCEPTANCE：Replay Gate（回测绑定字段齐全）与 Cloud Gate（发布证据）新增字段断言
- 相关：ADR-0010（表结构承载这些列）、ADR-0006（schema_version）
