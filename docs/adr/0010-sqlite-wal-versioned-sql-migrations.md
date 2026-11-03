# ADR-0010｜持久化：stdlib sqlite3 + WAL + 编号 SQL migration，靠 repository 接口预留 Postgres

状态：Accepted
日期：2026-11-03
关联任务：SYS-002、DATA-007、BT-006、API-002、OPS-003、DEP-003

## 背景

docs/02 §2 对持久化的表述是："SQLite WAL（MVP）→ PostgreSQL，**数据迁移预留接口**"；§4 目录里 `persistence/  # storage, migrations, snapshot lineage`。docs/02 §7 要求价格用 Decimal 或以字符串序列化，float 只能是中间值且不参与 tick/数量合规判定。docs/06 要求每次回测绑定 `git_commit`、`strategy_version`、`market_data_hash`、参数与费用/滑点假设。docs/09 要求 migration 可回退、每日备份保留 ≥7 份、升级失败先停 Worker 再确认 migration 可回退后才回滚 DB。

仓库任务书没有指定任何持久化库（无 SQLAlchemy、无 Alembic）。AGENTS.md §9 反对无依据引入昂贵新依赖，CLAUDE.md 要求优先标准库与既有依赖。

需要同时满足的约束：
1. MVP 单机、单 worker（docs/02 §6），SQLite 足够；
2. 必须预留 Postgres 迁移接口（DEP-003），且**不丢数据**；
3. schema 版本化与可回退是验收硬要求（ACCEPTANCE Cloud Gate、DATA-007）；
4. 决策/计划快照必须不可变并可追溯（docs/09 每次计划修订版本化）。

## 决策

1. **只用 Python 标准库 `sqlite3`**，不引入 ORM、不引入 Alembic。理由：表结构是任务书已经写死的固定集（docs/02 §7 约 15 张表），不存在"动态建模"收益；手写 SQL 让 SQLite/Postgres 差异显式可见，反而更利于 DEP-003；运行时依赖最小。
2. **连接配置**：`PRAGMA journal_mode=WAL`、`PRAGMA foreign_keys=ON`、`PRAGMA busy_timeout`（数值来自配置常量，不硬编码）、单 writer + 多 reader；写事务边界明确，失败回滚（CLAUDE.md 后端一致性条款）。
3. **编号 SQL migration**：`bfgi/persistence/migrations/0001_initial.sql … NN.sql`，up 与同名 `.down.sql` 成对存在；`schema_migrations(version, applied_at_utc)` 表记录已应用版本；migration runner 只按编号顺序执行、幂等（已应用版本跳过）、失败即整体回滚并退出非零。禁止在生产路径里做隐式 DDL。
4. **repository 接口层**：`bfgi/persistence/repositories.py` 定义 Protocol（`KlineRepository`、`ScanRunRepository`、`DecisionRepository`、`GridPlanRepository`、`BacktestRepository`、`AlertRepository`、`AuditRepository` 等），业务层只依赖 Protocol，不直接写 SQL。Postgres 适配（DEP-003）实现同一组 Protocol；共享 SQL 只使用可移植子集（不用 SQLite 特有语法；`INSERT ... ON CONFLICT DO NOTHING` 两者都支持）。
5. **存储类型规则**（docs/02 §7）：价格、数量、名义额一律 `TEXT`（十进制字符串，读取时转 `Decimal`）；时间一律 ISO-8601 UTC 字符串；只有明确命名的评分/统计列用 `REAL`，并且这些列不参与 tick/step/minNotional 合规判定。
6. **快照血缘**（snapshot lineage）：`scan_runs(scan_id, strategy_version, git_commit, snapshot_at_utc, market_data_hash, ...)` 为根，下游 `decisions`、`grid_plans`、`backtest_runs`、`alerts` 通过 `scan_id` / `plan_id` 关联，使任一结论可回溯到当时输入（DATA-007、BT-006）。
7. **不可变与幂等**：决策与计划快照不做 `UPDATE`；修订写新行到 `plan_revisions`（含 cause taxonomy，见 ADR-0011）。重复写入靠唯一约束 + `ON CONFLICT DO NOTHING` 实现幂等（含 `scan_runs(slot_at, strategy_version)`，见 ADR-0003、T-18）。
8. **保留与清理**：retention 7–30 天可配置（docs/03），清理任务只删可再生成的原始行情，不删 lineage 根记录与被引用的快照；清理前查询依赖，避免孤儿引用。
9. **备份/恢复**：`sqlite3 .backup` 等价实现（`sqlite3.Connection.backup`）+ 每日备份保留 ≥7 份（docs/09）；恢复演练脚本作为 DATA-007 验收证据。不备份 `.env`。

## 后果

- 正面：零新增运行时依赖；SQL 可见、可审计；SQLite→Postgres 的迁移面收敛在 repository 实现里，业务代码不变；migration 可回退可演练。
- 负面：手写 SQL 比 ORM 啰嗦，DDL 变更要走 migration 文件而不能改模型自动同步。这是刻意取舍：本项目的表结构稳定，审计性比开发便利更重要。
- 被否决的备选：SQLAlchemy ORM + Alembic（引入两套抽象，且任务书未要求；AGENTS.md §9）；直接让业务代码写 SQL（无法换 Postgres，违反"预留接口"）。

## 参考判断（jev，模型判断，非已验证事实）

choice `q_persistence_toolchain`：`stdlib_sqlite3_versioned_sql` 0.95（confidence 0.92），`sqlalchemy_core_alembic` 0.05，`sqlalchemy_orm` 0.00。与本地约束（任务书未指定库、最小依赖、表结构固定）一致，故采纳。

## 关联

- BACKLOG：DATA-007、DEP-003、BT-006、OPS-003
- ACCEPTANCE：Cloud Gate 的"备份恢复 + migration/rollback 演练"；新增门禁项"migration 回退演练有证据"
- 相关：ADR-0003（slot 幂等）、ADR-0011（版本身份与血缘字段）
