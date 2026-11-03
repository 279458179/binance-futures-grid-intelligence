# ADR 索引

架构决策记录（格式见 `0000-template.md`）。编号从 0001 起连续，永不复用或重排。
AGENTS.md §3 要求：与三套参考 skill 的冲突按**更严格的风险边界**解释并在 ADR 留痕——下表"冲突处理"列即留痕入口。

| 编号 | 标题 | 状态 | 决策要点 | 冲突处理 |
|---|---|---|---|---|
| 0001 | Monorepo 单包 `bfgi` | Accepted | docs/02 §4 的 `packages/*` 落地为 `bfgi/<name>` 子包 + `apps/api`/`apps/worker`/`apps/web`；CI 用 AST import 约束测试锁依赖方向 | docs/02 目录示意 ≠ 字面实现 |
| 0002 | 纯标准库指标内核 | Accepted | EMA/SMA/RSI14/ATR14/ADX14/Bollinger/RVOL/CVD_proxy/OI 变化自研；`Decimal` 走价格路径，Wilder 浮点标注为评分近似 | docs/02 "numpy/pandas 建议"、"TA-Lib 可选" → 不采纳为必需 |
| 0003 | APScheduler + DB slot lease | Accepted | 保留 docs/02 建议的 APScheduler；幂等由 `scan_runs(slot_at, strategy_version)` 唯一约束 + `worker_leases` 实现；追赶只补最后一个缺失 slot | 与"自研调度"备选冲突 → 尊重既有技术栈 |
| 0004 | Vite React SPA | Accepted | `apps/web` = Vite + React + TS，Caddy 静态托管，同源 `/api/v1`，`lightweight-charts`；Grid Planner 无下单按钮 | docs/02 主选 Next.js → docs/09 2GB VPS 构建内存警告更严格 |
| 0005 | 离线 fixtures 与 451 降级 | Accepted | 按文档化契约实现，冻结 fixtures 为验证基准；HTTP 451 是降级路径不是绕过理由；真实市场项标 `NOT_VERIFIED` | 地理限制 vs 交付进度 → 不绕过、不阻塞 |
| 0006 | 决策枚举与置信度词汇 | Accepted | 权威来源 `contracts/signal-example.json`；`decision` 5 值 + `direction_label` + `grid.direction`；置信度等级权威、数值由公开区间派生；`blockers` 与 `data_gaps` 两套；市场标识 `binance_usdm_usdt_perpetual` | direction-scout 与 grid-decision 词汇冲突 → 归一 + 映射表 |
| 0007 | 基准耦合闸门取并集 | Accepted | 定性硬闸门与定量耦合守卫并存，任一命中即阻断；相对强弱例外只恢复评分，不解除网格阻断 | 两套强度不同的规则 → 取更严格一侧 |
| 0008 | 分数不是概率 | Accepted | 禁用措辞词表进代码 + CI 扫描；LLM 只做解释且文本同样过校验；回测状态不许美化 | 参考 skill 措辞禁令 → 变成可执行测试 |
| 0009 | 只读边界是架构不变量 | Accepted | 无签名客户端、无 API key 配置项、公共端点白名单 CI 扫描、API/前端无下单入口负例测试 | AGENTS.md §6 → 结构性约束而非配置开关 |
| 0010 | SQLite WAL + 编号 SQL migration | Accepted | 标准库 `sqlite3`，无 ORM/Alembic；编号 up/down SQL + `schema_migrations`；repository Protocol 预留 Postgres；价格 TEXT、时间 ISO-8601 UTC | docs/02 未指定库 → 最小依赖 + 可移植接口 |
| 0011 | 版本身份与失败归因 | Accepted | `strategy_version` + `git_commit` + `market_data_hash` 必填；血缘链贯穿；失败必须记单一 primary cause 后才允许改参数 | docs/06 + grid-decision 归因要求 → 落成枚举 |

## 使用说明

- 新增 ADR：复制 `0000-template.md`，取下一个编号，在本表加一行。
- 状态变更：`Proposed` → `Accepted` / `Superseded by ADR-xxxx` / `Deprecated`；被取代时在旧文件状态行写明新编号。
- 业务行为变更（评分、闸门、网格参数、API/数据契约）必须新增 ADR 或更新 PRD/BACKLOG（AGENTS.md §10），不能只改代码。
