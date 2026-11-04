# 任务变更记录（AGENTS.md §10）

每个合并/提交按 Task ID 记录：改变了什么 API/策略、测试证据、风险、迁移与回滚、已知缺口。倒序排列。

---

## 2026-11-04｜SYS-004：apps/api 最小入口（Settings 注入 + 错误信封 + 只读兜底）

**Task ID**：SYS-004（API 最小入口步；完整 SYS-004 范围含 timeutil/version/enums/hashing/schemas 定向单测，见 `planning/SYS-004.md` 已知缺口）

**改变了什么 API/策略**
- 新增 `apps/api/app.py`（ADR-0012）：`create_app(settings=None, *, env=None, dotenv_file=None)`；配置构造期读一次、缓存 `app.state.settings`、`SettingsDep` 注入；`/healthz`；统一错误信封 `{"error": {"code", "message", "request_id"}}`（校验错误可带 `violations`，仅 loc+type）；ErrorCode→HTTP 状态与固定文案表在 apps/；404/405 → `CONTRACT_VIOLATION` 永不 500（T-22）；纯 ASGI `ReadOnlyGuardMiddleware` 把交易意图路径拦成 404（非 403），审计 `read_only_guard.blocked` 只记 method/path/UTC/request_id。
- 新增 `tests/test_app_settings.py`：6 条冻结契约 + 2 条架构守卫（AST import 扫描：`bfgi/core` 永不 import HTTP 框架/apps；load-once 可被单测计数证明）。
- 新增 ADR-0012 + 索引行；`pyproject.toml`：`[tool.mypy] packages = ["bfgi", "apps"]`；`[tool.ruff.lint] allowed-confusables`（中文全角标点白名单，RUF001/002/003 对真正混淆字符仍拦截）。
- 无策略、无信号、无交易面变更；`orders_placed` 恒 false（ADR-0009 不变量，代码常量而非配置推断）。

**测试**
- `pytest`：148 passed，1 warning（`StarletteDeprecationWarning`，fastapi 自带 testclient.py:1 触发，环境因素）。
- `mypy`（strict）：Success，14 source files。
- `ruff check apps/api/app.py tests/test_app_settings.py pyproject.toml`：0.15.6（已安装）与 0.11.13（声明范围 venv）均 0 违规。
- 全仓 `ruff check .`：0.15.6 口径 104 条（E501×97 + 7 条遗留，全部在既有文件，非本步引入）；0.11.13 口径 107（多 3 条 UP038）。全仓 E501 位置集合两版本逐行一致（diff 为空）——E501 属既有线宽问题，与 ruff 版本无关。

**风险**
- 依赖漂移：已安装 fastapi 0.141.1 / uvicorn 0.52.1 / structlog 26.1.0 / pytest 9.0.2 / ruff 0.15.6 超出 pyproject 上界；**未升级、未放宽声明**，治理走 `planning/ADMIN-002.md`（Proposed，待立项）。
- 500 无统一信封（taxonomy 无 `INTERNAL`；新增错误码需先改 taxonomy + ADR，AGENTS.md §10）。
- 守卫词表含 `cancel`/`account` 等：未来合法路由撞词需先评审（ADR-0012 后果节）。

**迁移 / 回滚**
- 无数据迁移、无生产部署。回滚 = `git revert` 本提交并删除 `apps/` 与 pyproject 相关行。

**已知缺口**
- `uvicorn --factory` 未实跑（仓库无 `.env`，无参 `create_app()` 按 config.py 既定语义 CONFIG_ERROR fail-closed，属预期入口缺口；`main.py` 传 `os.environ` 归 API-001）。
- `tests/test_timeutil.py`、`tests/test_version.py`、enums/hashing/schemas 定向单测未补（SYS-004 剩余范围）。
- `bfgi/core/version.py` docstring 声称的 `tests/unit/test_version.py` 不存在（文档漂移，随上述测试修正）。
- 既有文件 lint 遗留 104/107 条清单见 `planning/ADMIN-002.md`，不在本步修（范围纪律）。

**诚实记录**
- 此前会话"ruff 通过"的说法指本任务文件范围（新增文件两版本 0 违规），按全仓口径不成立，特此更正。
- jev `choice` 接口不可用（9 种 payload 全报 `choice needs 2-255 criteria options`），ADR-0012 改用 `score` 口径（A 1.18/4、B 2.64/4、纯 ASGI 守卫 3.47/4，jev-1.14.0）；本步 ruff 治理策略 jev：fit_A 2.05（conf 0.28）/ fit_B 2.91 / fit_C 2.87，A_over_C 0.88，fix_e501_now 0.26 → 采用 A（allowed-confusables），存量 E501 不强行修，走 ADMIN-002。jev 输出为参考判断，非已验证事实。
- Binance 公共 API 在本地返回 HTTP 451（地区受限）→ 真实市场验证项保持 `NOT_VERIFIED`（ADR-0005）。
- 仓库出现未提交的 `planning/WRITE_PROBE.md`（内容 "write probe / probe-created"，非本任务产物）：未纳入本次提交，保留在工作区待你处置。

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
