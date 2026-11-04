# ADR-0012｜API 入口位置、Settings 注入与错误信封

状态：Accepted
日期：2026-11-04
关联任务：SYS-004（API-001 依赖它）

## 背景

ADR-0001 只定了 `apps/api` 是进程入口，没有定三件实现层的事：配置在哪个生命周期读取、
ErrorCode→HTTP 状态映射表放在哪一层、只读兜底（ADR-0009）在哪个环节拦截。实现 `apps/api/app.py`（SYS-004）
时出现两组分叉：

- A：配置/入口放 `bfgi/core/api/`，请求路径上按需加载；B：入口在 `apps/api`，配置在构造期读一次并缓存。
- 拦截方式：`BaseHTTPMiddleware` vs 纯 ASGI 守卫；交易意图返回 403 vs 404。

（jev `choice` 接口不可用——9 种 payload 全部报 `choice needs 2-255 criteria options`，改用 `score`：
A 1.18/4、B 2.64/4、纯 ASGI 守卫 3.47/4，jev-1.14.0。jev 判断只作为参考输入，结论以下列项目约束为准。）

决定性约束是既有事实，不是偏好：

- AST 依赖方向测试（ADR-0001）禁止 `bfgi/core` import fastapi/starlette/structlog/apps——`bfgi/core/api` 直接违规。
- 仓库没有 `.env`：`load_settings_from_env(env=None)` 不读 `os.environ`（config.py 既定语义），
  import 期构造 app 会让 pytest 收集阶段直接 `CONFIG_ERROR`。
- 403 告诉探测方"该端点存在但被禁止"，404 才能把交易端点伪装成"不存在"（ACCEPTANCE T-22 只禁止 500）。

## 决策

1. `apps/api` 是唯一 HTTP 入口；`bfgi/core` 永不 import HTTP 框架或 `apps/`，由 AST 测试强制
   （`tests/test_app_settings.py::test_core_never_imports_http_or_apps_layers`）。
2. 配置只在 `create_app` 构造期读取一次，缓存在 `app.state.settings`，端点通过
   `SettingsDep = Annotated[Settings, Depends(get_settings)]` 注入；请求路径上不得重复加载。
3. `create_app(settings=None, *, env=None, dotenv_file=None)`；模块级没有 app 实例，
   启动方式固定为 `uvicorn --factory apps.api.app:create_app`。配置错误在构造期抛出（fail-closed）。
4. 统一错误信封 `{"error": {"code", "message", "request_id"}}`（校验错误可带 `violations`，只含
   `loc`+`type`）；ErrorCode→HTTP 状态与固定文案两张映射表放 `apps/api`；`BfgiError.details`、
   校验输入、`BfgiError.message` 一律不回显。
5. 404/405 一律映射 `CONTRACT_VIOLATION`，永不冒 500（T-22）。交易意图路径在路由前由纯 ASGI
   守卫拦截为 404（不是 403），审计事件 `read_only_guard.blocked` 只记 method/path/UTC/request_id，
   绝不记 query/body。
6. 把真实 `os.environ` 传进 `create_app(env=...)` 的进程入口 `main.py` 归 API-001，本轮不做。

## 后果

- 正面：pytest 不依赖 `.env`；配置加载次数可被单测计数证明"只读一次"；错误信封形状稳定；
  交易探测得到与"路径不存在"无法区分的响应。
- 负面/缺口：未预期异常仍是 FastAPI 默认 500（无信封）——ErrorCode taxonomy 没有 `INTERNAL`，
  新增错误码要先改 taxonomy + ADR（AGENTS.md §10），本轮不越权。
- 守卫词表含 `cancel`/`account` 等词：未来任何合法路由名撞这些词都要先评审（增删词 = 改变只读边界）。
- 映射表与守卫会被 API-001 扩展（鉴权 401/403、限流 429 的真实映射）；本 ADR 只冻结形状与不变量，
  不冻结完整 API 面。
- 不用 `BaseHTTPMiddleware`：安装的 starlette（1.6.0）与 pyproject 声明范围漂移，纯 ASGI 守卫对版本最不敏感。

## 关联

- BACKLOG 任务 ID：SYS-004（本轮）；API-001（消费方）；OPS-004（structlog 全局配置、/readyz）。
- ACCEPTANCE 门禁 / T-xx：T-22（任何端点探测不得 500）；ADR-0009 §5（`orders_placed` 恒 false、审计字段限定）。
- 参考 skill 文件：无直接冲突；AGENTS.md §6 的只读边界是本 ADR 的上游约束。
- 被否决的备选：
  - `bfgi/core/api/`（ADR-0001 依赖方向禁止）；
  - 请求期加载配置（重复 I/O，且无法用测试证明"只读一次"）；
  - `BaseHTTPMiddleware`（声明/安装版本漂移）；
  - 403 拦截（泄露端点存在性）；
  - 本轮直接实现完整 API-001（越序，AGENTS.md §2 要求一次 PR 只处理一个合理依赖闭包）。
