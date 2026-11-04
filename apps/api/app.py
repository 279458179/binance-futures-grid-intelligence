"""apps/api：FastAPI 入口（SYS-004 / ADR-0012）。

本模块只做三件事（都不是业务功能，业务端点归 API-001）：
1. 配置在 **构造期** 读取一次，缓存在 ``app.state``，通过 ``Depends`` 注入（ADR-0012）；
   请求路径上不允许重复加载配置。
2. 统一错误信封 ``{"error": {"code", "message", "request_id"}}``：错误码到 HTTP 状态的映射表在
   apps/，``BfgiError.details`` 与校验输入 **永不回显**（ADR-0009）。
3. 运行时只读兜底（ADR-0009 §5 / ACCEPTANCE T-22）：交易意图路径在路由前 404，
   审计只记录 method/path/UTC/request_id，绝不记录 query/body。

不在本轮范围（API-001 / OPS-004）：业务 schema、鉴权、限流、/readyz、metrics、structlog 全局配置。

启动方式（ADR-0012）：``uvicorn --factory apps.api.app:create_app``。
模块级没有 app 实例——仓库当前没有 .env，import 期加载配置会让 pytest 直接崩。

已知缺口：``create_app()`` 无参调用时走 ``load_settings_from_env(env=None)``，只读
``.env``/``.env.local``，不读 ``os.environ``（config.py 的既定语义）；真实进程入口把
``os.environ`` 传进来的 ``main.py`` 归 API-001。
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, cast

import structlog
from bfgi.core import config
from bfgi.core.config import Settings
from bfgi.core.constants import MARKET_ID, SCHEMA_VERSION
from bfgi.core.errors import BfgiError, ErrorCode
from bfgi.core.timeutil import format_utc, utc_now
from bfgi.core.version import STRATEGY_VERSION
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger("bfgi.api")  # structlog 全局配置归 OPS-004，这里不 configure

# ADR-0009 §5：orders_placed 运行时恒为 false，写成常量而不是从配置推断。
ORDERS_PLACED_INVARIANT: bool = False

# 状态映射表在 apps/（ADR-0012）：错误码语义属于领域层，HTTP 状态属于 HTTP 层。
# 交易意图在守卫里被拦成 404；表里的 403 只覆盖业务层显式抛 READ_ONLY_VIOLATION 的情况。
ERROR_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_VALUE: 422,
    ErrorCode.INVALID_DECIMAL: 422,
    ErrorCode.INVALID_TIME: 422,
    ErrorCode.CONTRACT_VIOLATION: 422,
    ErrorCode.CONFIG_ERROR: 500,
    ErrorCode.READ_ONLY_VIOLATION: 403,
    ErrorCode.STALE_DATA: 503,
    ErrorCode.DATA_GAP: 503,
    ErrorCode.PROVIDER_RATE_LIMITED: 429,
    ErrorCode.PROVIDER_BANNED: 429,
    ErrorCode.PROVIDER_GEO_BLOCKED: 503,
    ErrorCode.PROVIDER_SERVER_ERROR: 502,
    ErrorCode.PROVIDER_CLIENT_ERROR: 502,
    ErrorCode.PROVIDER_TRANSPORT_ERROR: 502,
    ErrorCode.PROVIDER_SCHEMA_DRIFT: 502,
}

# 固定文案：绝不回显 BfgiError.message（details/内部文案可能含字段值，ADR-0009）。
ERROR_MESSAGE_BY_CODE: dict[ErrorCode, str] = {
    ErrorCode.INVALID_VALUE: "请求参数不在允许范围内",
    ErrorCode.INVALID_DECIMAL: "价格或数量字段不合法",
    ErrorCode.INVALID_TIME: "时间字段不合法（所有时间必须是 UTC）",
    ErrorCode.CONTRACT_VIOLATION: "请求不匹配任何已实现的接口契约",
    ErrorCode.CONFIG_ERROR: "服务端配置无效",
    ErrorCode.READ_ONLY_VIOLATION: "本系统只读：不提供交易、撤单、划转或杠杆类接口",
    ErrorCode.STALE_DATA: "市场数据已过期，暂不给出结论",
    ErrorCode.DATA_GAP: "市场数据缺口过大，暂不给出结论",
    ErrorCode.PROVIDER_RATE_LIMITED: "上游行情接口限流",
    ErrorCode.PROVIDER_BANNED: "上游行情接口拒绝访问",
    ErrorCode.PROVIDER_GEO_BLOCKED: "上游行情接口在当前地区不可用",
    ErrorCode.PROVIDER_CLIENT_ERROR: "上游行情接口返回异常",
    ErrorCode.PROVIDER_SERVER_ERROR: "上游行情接口暂时不可用",
    ErrorCode.PROVIDER_SCHEMA_DRIFT: "上游行情接口返回结构与契约不符",
    ErrorCode.PROVIDER_TRANSPORT_ERROR: "上游行情接口连接失败",
}

# 整段路径（大小写不敏感）命中即拦截。故意不含 trade/trades（docs/03 公共端点）与裸 close；
# 保留 cancel。每次增删词 = 扩大/收窄只读边界，需评审（AGENTS.md §10）。
TRADING_INTENT_SEGMENTS: frozenset[str] = frozenset(
    {
        "order", "orders", "orderrate", "openorder", "openorders", "allorders", "neworder",
        "placeorder", "submitorder", "modifyorder", "cancel", "cancelorder", "cancelall",
        "closeall", "closeposition", "mytrade", "mytrades", "buy", "sell", "position",
        "positions", "positionrisk", "adlquantile", "leverage", "margin", "margintype",
        "isolatedmargin", "forcedliquidation", "forcerecords", "transfer", "withdraw",
        "withdrawal", "deposit", "subaccount", "convert", "account", "accountinfo",
        "balance", "balances", "asset", "assets", "income", "commissionrate",
        "listenkey", "userstream",
    }
)


def is_trading_intent_path(path: str) -> bool:
    """路径任意一段命中交易意图词即视为交易意图（大小写不敏感）。"""
    return any(segment.lower() in TRADING_INTENT_SEGMENTS for segment in path.split("/") if segment)


def _ascii(value: object) -> str:
    """Windows GBK 控制台加固：非 ASCII 以转义形式落日志，不让日志写出本身崩。"""
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _audit(event: str, request_id: str, method: str, path: str, **extra: object) -> None:
    """只记 method/path/UTC/request_id（ADR-0009 §5）。绝不记录 query 与 body。"""
    fields = {key: _ascii(val) for key, val in extra.items()}
    logger.info(
        event,
        request_id=request_id,
        method=_ascii(method),
        path=_ascii(path),
        checked_at=format_utc(utc_now()),
        **fields,
    )


def _request_id() -> str:
    return uuid.uuid4().hex


def _envelope(
    code: ErrorCode,
    request_id: str,
    *,
    status: int | None = None,
    violations: list[dict[str, str]] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {
        "code": code.value,
        "message": ERROR_MESSAGE_BY_CODE[code],
        "request_id": request_id,
    }
    if violations is not None:
        error["violations"] = violations
    status_code = status if status is not None else ERROR_STATUS_BY_CODE[code]
    return JSONResponse(status_code=status_code, content={"error": error})


class ReadOnlyGuardMiddleware:
    """纯 ASGI 守卫（不用 BaseHTTPMiddleware：声明/安装版本存在漂移）。

    交易意图在路由前直接 404——不是 403：探测方无法区分"被隐藏的端点"与"不存在的路径"，
    403 会泄露端点存在性。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        if not is_trading_intent_path(path):
            await self.app(scope, receive, send)
            return
        request_id = _request_id()
        _audit(
            "read_only_guard.blocked",
            request_id,
            str(scope.get("method", "")),
            path,
            code=ErrorCode.READ_ONLY_VIOLATION.value,
        )
        response = _envelope(ErrorCode.READ_ONLY_VIOLATION, request_id, status=404)
        await response(scope, receive, send)


def _violations(exc: RequestValidationError) -> list[dict[str, str]]:
    """丢弃 msg/input/ctx：input 可能带敏感输入值（ADR-0009）。"""
    return [
        {
            "loc": _ascii(".".join(str(part) for part in error.get("loc", ()))),
            "type": _ascii(error.get("type", "")),
        }
        for error in exc.errors()
    ]


def install_error_handlers(app: FastAPI) -> None:
    """可独立测试的注册函数（SYS-004 测试直接对探针 app 调用它）。

    未预期异常不注册 catch-all：ErrorCode taxonomy 没有 INTERNAL，凭空发明错误码要先改
    taxonomy + ADR（AGENTS.md §10），这里不越权——500 无统一信封是已记录的缺口。
    """

    @app.exception_handler(BfgiError)
    async def handle_bfgi_error(request: Request, exc: Exception) -> JSONResponse:
        # 运行时不可达的窄化：FastAPI 按注册类型分发，mypy strict 需要显式窄化才能取属性。
        if not isinstance(exc, BfgiError):
            raise exc
        request_id = _request_id()
        # details 可能含字段值：绝不回显，也不落日志（ADR-0009）。
        _audit("api.error", request_id, request.method, request.url.path, code=exc.code.value)
        return _envelope(exc.code, request_id)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: Exception) -> JSONResponse:
        # FastAPI 的 HTTPException 就是 StarletteHTTPException，注册一次即可覆盖两者。
        if not isinstance(exc, StarletteHTTPException):
            raise exc
        request_id = _request_id()
        status = exc.status_code
        if status in (404, 405):
            # 已规划未实现的写入端点（POST /api/v1/scans）与方法不匹配（POST /healthz）都走
            # 404/405 信封而不是 500（T-22），但不得标成交易违规。401/403/429 类映射归 API-001。
            _audit("api.unmatched", request_id, request.method, request.url.path, status=status)
        else:
            _audit("api.http_error", request_id, request.method, request.url.path, status=status)
        return _envelope(ErrorCode.CONTRACT_VIOLATION, request_id, status=status)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RequestValidationError):
            raise exc
        request_id = _request_id()
        # 审计必须引用 request：ruff ARG 已启用，未用参数会报 ARG001。
        _audit(
            "api.validation",
            request_id,
            request.method,
            request.url.path,
            error_count=len(exc.errors()),
        )
        return _envelope(
            ErrorCode.CONTRACT_VIOLATION,
            request_id,
            status=422,
            violations=_violations(exc),
        )


def get_settings(request: Request) -> Settings:
    """构造期缓存的 Settings；配置不在请求路径上重复加载（ADR-0012）。"""
    return cast(Settings, request.app.state.settings)


# Annotated + 变量绑定：避免 B008（默认参数里调函数）与 Default= 弃用写法。
SettingsDep = Annotated[Settings, Depends(get_settings)]


def create_app(
    settings: Settings | None = None,
    *,
    env: Mapping[str, str] | None = None,
    dotenv_file: str | Path | None = None,
) -> FastAPI:
    """构造 FastAPI app。配置至多读取一次，缓存在 app.state（ADR-0012）。

    走模块属性 ``config.`` 查找，便于测试 monkeypatch 计数；配置错误在构造期抛出
    （docs/02 §4：入口 fail-closed）。
    """
    resolved = settings
    if resolved is None:
        resolved = config.load_settings_from_env(env=env, dotenv_file=dotenv_file)

    app = FastAPI(
        title="Binance Futures Grid Intelligence API",
        version=STRATEGY_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved
    app.add_middleware(ReadOnlyGuardMiddleware)
    install_error_handlers(app)

    @app.get("/healthz", response_model=None)
    async def healthz(current: SettingsDep) -> dict[str, object]:
        # /readyz（依赖探测）与 metrics 归 OPS-004；
        # 完整 VersionIdentity（git_commit）归 API-001/OPS。
        return {
            "status": "ok",
            "app_env": current.app_env,
            "market_id": MARKET_ID,
            "schema_version": SCHEMA_VERSION,
            "strategy_version": STRATEGY_VERSION,
            "scan_interval_minutes": current.market_scan_interval_minutes,
            "read_only": current.futures_only_read_only,
            "orders_placed": ORDERS_PLACED_INVARIANT,
            "config_warnings": list(current.warnings),
            "checked_at": format_utc(utc_now()),
        }

    return app
