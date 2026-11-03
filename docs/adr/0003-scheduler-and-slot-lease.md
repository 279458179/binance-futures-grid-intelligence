# ADR-0003｜调度触发沿用 APScheduler，幂等由独立的 DB 槽位租约层保证

状态：Accepted（取代本 ADR 的早期草案"自研 asyncio 调度器替换 APScheduler"）
日期：2026-11-03
关联任务：OPS-001、SYS-002

## 背景

docs/02 §2 建议 worker 使用 APScheduler。OPS-001 的完成标准是"无重复任务，重启可恢复"；docs/02 §6 要求单 worker 部署、重复写入幂等、将来加副本需分布式锁/租约。

关键分析：无论用什么触发器，OPS-001 需要的机制都是同一个——**按 UTC 槽位（15M 边界）做幂等 + 跨进程租约**。调度器只决定"什么时候尝试"，幂等必须落在持久层。因此"换掉调度器"并不能解决 OPS-001，反而会引入自定义调度代码（错过槽位、漂移、心跳、租约续期都要自己写并自己测）。

判断输入（`mcp__jev_judgment__judge`，jev-1.14.0，模型判断非事实）两次提问结果矛盾：第一次 `asyncio_slot_db_lease` 0.74（confidence 0.48）；第二次给出完整约束后 `apscheduler_plus_lease` 0.61（confidence 0.22）。jev 在该项上不稳定，不作为决策依据。

## 决策

- **沿用 docs/02 建议的 APScheduler**（`AsyncIOScheduler`）作为周期触发器：15M 扫描、30min 衍生数据刷新、每日保留期清理。不擅自替换任务书建议的技术栈。
- **幂等与租约独立实现于 `bfgi/persistence`**，与调度器实现解耦：
  - 槽位标识 `slot_at` = 对齐到 15M 边界的 UTC 时间，不依赖进程启动时间。
  - `scan_runs(slot_at, strategy_version)` 上有唯一约束：同一槽位重复触发直接命中已存在记录并跳过（`INSERT ... ON CONFLICT DO NOTHING`）。
  - `worker_leases(lease_key, slot_at, holder, acquired_at, expires_at, heartbeat_at)`：执行前抢租约，过期租约（`expires_at < now`）可被重新抢占；心跳随扫描进度更新。
- 启动时 catch-up **只补最近一个未完成槽位**，不追赶历史积压（重启后不打爆 API 权重，docs/03 §限速）。
- 副本扩展：`lease_key` 持久层语义不变，切换到 Postgres 行锁（docs/02 §7 迁移路径），调度与扫描代码不变。

## 后果

- 正面：不偏离任务书；OPS-001 的验收点是可测的数据库不变量（同一 `slot_at` 只有一条 `scan_runs`），而不是调度器行为；调度器若将来要换，幂等层不受影响。
- 负面：多一个依赖（APScheduler）。属于成熟轻量依赖，不违反 AGENTS.md §9（禁止"昂贵依赖"）。
- 被否决的备选：自研 asyncio 调度循环（要自己实现错过槽位/漂移/心跳，等于重复实现调度器，且偏离任务书）。

## 参考判断（jev，模型判断，非已验证事实）

同一问题两次结果不一致（0.74 vs 0.39 支持自研；0.61 支持 APScheduler+租约），置信度均低。本 ADR 明确不采纳 jev 结论作为依据，改用本地约束推理：租约层无论如何都要写，换调度器不减少代码量也不减少风险。**这一取舍已上报，用户可复议。**

## 关联

- BACKLOG：OPS-001（无重复任务、重启可恢复）、SYS-002（依赖锁定）
- ACCEPTANCE：同一槽位重复启动只产生一条 `scan_runs`；重启只补一个槽位
- 被否决的备选：自研 asyncio 调度器；系统 cron 启动一次性进程（丢失进程内权重预算与缓存）
