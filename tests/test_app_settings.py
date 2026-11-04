"""SYS-004 冻结测试：apps/api 入口契约（ADR-0012 / ADR-0009 / ACCEPTANCE T-22）。

冻结的契约：
1. 配置只在 create_app 构造期读取一次，缓存在 app.state，经由 Depends 注入；请求路径不得重复加载。
2. 错误一律走信封 {"error": {"code", "message", "request_id"}}；BfgiError.details 与输入永不回显。
3. 交易意图路径在路由前 404（不是 403：403 会暴露端点存在性）；审计只记 method/path/UTC/request_id，
   绝不记 query/body。
4. 已规划未实现的端点 → 404 CONTRACT_VIOLATION；方法不匹配 → 404 或 405；
   任何探测不得出现 500（T-22）。
5. 路由表与 OpenAPI 里没有交易路径，也没有写操作。
6. import apps.api.app 不加载配置、不构造 app（模块级没有 app / main）。

架构守卫（@pytest.mark.architecture，ADR-0001 / ADR-0012）：
bfgi/core 不得 import HTTP 层或 apps/；apps/ 只允许 import bfgi、HTTP 框架、structlog 与标准库。
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

import apps.api.app as api_module
import pytest
from apps.api.app import (
    ERROR_MESSAGE_BY_CODE,
    ERROR_STATUS_BY_CODE,
    ORDERS_PLACED_INVARIANT,
    TRADING_INTENT_SEGMENTS,
    create_app,
    install_error_handlers,
    is_trading_intent_path,
)
from bfgi.core.config import Settings, load_settings_from_env, parse_dotenv
from bfgi.core.errors import BfgiError, ErrorCode
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# 与 tests/test_config.py 各自持有一份而不跨文件 import：测试辅助跨文件共享会形成隐式依赖链。
SENTINEL = "SENTINEL-VALUE-MUST-NOT-BE-LOGGED-4f31"

TRADING_PROBES: tuple[str, ...] = (
    "/api/v1/orders",
    "/orders",
    "/api/v1/openOrders",
    "/api/v1/positionRisk",
    "/api/v1/account",
    "/api/v1/leverage",
    "/api/v1/transfer",
    "/API/V1/ORDERS",  # 大小写不敏感：守卫按小写段匹配
)

# docs/03 规划但本轮未实现的端点：必须表现为"不存在"（404），不得表现为 500（T-22）。
PLANNED_PROBES: tuple[str, ...] = (
    "/api/v1/scans",
    "/api/v1/candidates",
    "/api/v1/grid-plans",
    "/api/v1/backtests",
    "/api/v1/alerts",
    "/api/v1/settings",
    "/api/v1/market/summary",
    "/api/v1/symbols/BTCUSDT/analysis",
    "/api/v1/scans/scan-1",
)

# docs/03 公共行情端点用词（aggTrades/trades/ticker）不是交易意图——守卫故意不拦这些词。
PUBLIC_MARKET_PROBES: tuple[str, ...] = (
    "/api/v1/market/aggTrades",
    "/api/v1/market/trades",
    "/api/v1/market/ticker/24hr",
)

CORE_FORBIDDEN: frozenset[str] = frozenset(
    {"fastapi", "starlette", "uvicorn", "structlog", "httpx", "apps"}
)
API_ALLOWED: frozenset[str] = (
    frozenset({"bfgi", "apps", "fastapi", "starlette", "uvicorn", "structlog"})
    | frozenset(sys.stdlib_module_names)
)


def base_env(**overrides: str) -> dict[str, str]:
    """以 .env.example 为基线构造配置（不复制常量，避免样例与测试漂移）。"""
    env = parse_dotenv(ENV_EXAMPLE.read_text(encoding="utf-8"))
    env.update(overrides)
    return env


def settings_from_example(**overrides: str) -> Settings:
    """显式 dotenv_file=仓库样例：测试不受运行目录里偶然存在的 .env 影响。"""
    return load_settings_from_env(env=base_env(**overrides), dotenv_file=ENV_EXAMPLE)


def build_app(**overrides: str) -> FastAPI:
    return create_app(settings=settings_from_example(**overrides))


# ---------------------------------------------------------------- 契约 1

def test_healthz_reports_read_only_invariants() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["orders_placed"] is False
    assert ORDERS_PLACED_INVARIANT is False
    assert body["read_only"] is True
    assert body["app_env"] == "development"
    assert body["checked_at"].endswith("Z")


def test_settings_are_loaded_exactly_once_at_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """配置在构造期读一次并缓存；请求路径不得再读（ADR-0012）。"""
    original = load_settings_from_env
    calls: list[int] = []

    def counting_loader(env: object = None, dotenv_file: object = None) -> Settings:
        calls.append(1)
        return original(env=env, dotenv_file=dotenv_file)

    monkeypatch.setattr("bfgi.core.config.load_settings_from_env", counting_loader)
    app = create_app(dotenv_file=ENV_EXAMPLE)
    assert len(calls) == 1

    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/healthz").status_code == 200
    assert len(calls) == 1
    assert isinstance(app.state.settings, Settings)


def test_injected_settings_skip_config_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """settings= 注入后，create_app 内部不得再触发配置加载。"""

    def forbidden_loader(*_args: object, **_kwargs: object) -> Settings:
        raise AssertionError("create_app(settings=...) 不应触发配置加载（ADR-0012）")

    monkeypatch.setattr("bfgi.core.config.load_settings_from_env", forbidden_loader)
    app = create_app(settings=settings_from_example(MARKET_SCAN_INTERVAL_MINUTES="20"))
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["scan_interval_minutes"] == 20
    assert any("MARKET_SCAN_INTERVAL_MINUTES=20" in m for m in body["config_warnings"])


def test_create_app_rejects_credential_env_without_leaking_value() -> None:
    """配置错误在构造期抛出（fail-closed），且哨兵值不进 details。"""
    with pytest.raises(BfgiError) as excinfo:
        create_app(env=base_env(BINANCE_FUTURES_API_KEY=SENTINEL))
    error = excinfo.value
    assert error.code is ErrorCode.READ_ONLY_VIOLATION
    assert SENTINEL not in json.dumps(error.to_dict(), ensure_ascii=False)


def test_create_app_rejects_bad_database_url() -> None:
    with pytest.raises(BfgiError) as excinfo:
        create_app(env=base_env(DATABASE_URL="postgresql://user@host/db"))
    assert excinfo.value.code is ErrorCode.CONFIG_ERROR


# ---------------------------------------------------------------- 契约 5

def test_no_trading_routes_and_no_write_operations() -> None:
    app = build_app()
    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    paths = sorted({route.path for route in api_routes})
    assert paths == ["/healthz"]
    for route in api_routes:
        assert route.methods <= {"GET"}
        segments = {segment for segment in route.path.split("/") if segment}
        assert segments & TRADING_INTENT_SEGMENTS == set()
    schema = app.openapi()
    assert set(schema["paths"]) == {"/healthz"}
    assert set(schema["paths"]["/healthz"]) == {"get"}


# ---------------------------------------------------------------- 契约 3

@pytest.mark.parametrize("path", TRADING_PROBES)
def test_trading_intent_paths_are_blocked_with_404_not_403(path: str) -> None:
    with TestClient(build_app()) as client:
        response = client.post(path, json={"secret_symbol": SENTINEL})
    # 交易意图必须表现为"不存在"，不是"已实现但禁止"。
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == ErrorCode.READ_ONLY_VIOLATION.value
    assert error["message"] == ERROR_MESSAGE_BY_CODE[ErrorCode.READ_ONLY_VIOLATION]
    assert error["request_id"]
    assert "details" not in error
    assert SENTINEL not in response.text


def test_guard_audit_shape_and_no_body_leak() -> None:
    app = build_app()
    with TestClient(app) as client, capture_logs() as logs:
        response = client.post("/api/v1/orders", json={"secret_symbol": SENTINEL})
    assert response.status_code == 404
    blocked = [entry for entry in logs if entry["event"] == "read_only_guard.blocked"]
    assert len(blocked) == 1
    entry = blocked[0]
    assert entry["method"] == "POST"
    assert entry["path"] == "/api/v1/orders"
    assert entry["request_id"]
    assert entry["checked_at"].endswith("Z")
    assert SENTINEL not in json.dumps(logs, ensure_ascii=False, default=str)

    with TestClient(app) as client, capture_logs() as logs:
        assert client.get("/healthz").status_code == 200
    assert [entry for entry in logs if entry["event"] == "read_only_guard.blocked"] == []


# ---------------------------------------------------------------- 契约 4

@pytest.mark.parametrize("path", PLANNED_PROBES)
def test_planned_but_unimplemented_endpoints_return_404_contract_envelope(path: str) -> None:
    with TestClient(build_app()) as client, capture_logs() as logs:
        response = client.post(path, json={"symbol": "BTCUSDT"})
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == ErrorCode.CONTRACT_VIOLATION.value
    assert error["code"] != ErrorCode.READ_ONLY_VIOLATION.value
    assert any(entry["event"] == "api.unmatched" for entry in logs)


def test_method_mismatch_never_returns_500() -> None:
    """T-22 接受 404 或 405（Starlette 方法不匹配的实现细节），唯一禁止的是 500。"""
    with TestClient(build_app()) as client:
        response = client.post("/healthz", json={})
    assert response.status_code in {404, 405}
    error = response.json()["error"]
    assert error["code"] == ErrorCode.CONTRACT_VIOLATION.value
    assert error["request_id"]


@pytest.mark.parametrize("path", TRADING_PROBES + PLANNED_PROBES)
def test_t22_no_probe_ever_reaches_500(path: str) -> None:
    with TestClient(build_app()) as client:
        response = client.post(path, json={"symbol": "BTCUSDT"})
    assert response.status_code in {404, 405}
    error = response.json()["error"]
    allowed = {ErrorCode.READ_ONLY_VIOLATION.value, ErrorCode.CONTRACT_VIOLATION.value}
    assert error["code"] in allowed
    assert "BTCUSDT" not in response.text


# ---------------------------------------------------------------- 只读边界的宽度

@pytest.mark.parametrize("path", PUBLIC_MARKET_PROBES)
def test_public_market_terms_are_not_blocked_by_guard(path: str) -> None:
    """守卫不收窄 docs/03 的公共行情面：aggTrades/trades/ticker 必须放行到路由层（本轮 404）。"""
    assert is_trading_intent_path(path) is False
    with TestClient(build_app()) as client:
        response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == ErrorCode.CONTRACT_VIOLATION.value


# ---------------------------------------------------------------- 契约 2

def test_error_tables_cover_every_error_code() -> None:
    members = list(ErrorCode)
    assert members
    assert set(ERROR_STATUS_BY_CODE) == set(ERROR_MESSAGE_BY_CODE) == set(members)
    for code in members:
        assert 400 <= ERROR_STATUS_BY_CODE[code] < 600
        assert ERROR_MESSAGE_BY_CODE[code].strip()


def test_validation_error_envelope_shape() -> None:
    """探针路由存在的原因：apps/api 没有带参数的业务路由；
    为了测试给生产代码加空壳端点属于"空壳功能"，禁止。"""
    probe = FastAPI()
    install_error_handlers(probe)

    @probe.get("/probe")
    async def probe_route(limit: int = 1) -> dict[str, object]:
        return {"limit": limit}

    with TestClient(probe) as client:
        response = client.get("/probe", params={"limit": SENTINEL})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == ErrorCode.CONTRACT_VIOLATION.value
    assert error["violations"] == [{"loc": "query.limit", "type": "int_parsing"}]
    assert "details" not in error
    assert SENTINEL not in response.text


# ---------------------------------------------------------------- 契约 6

def test_module_has_no_import_time_app_or_main() -> None:
    """import apps.api.app 不得加载配置、不得构造 app（uvicorn --factory 的前提）。"""
    assert not hasattr(api_module, "app")
    assert not hasattr(api_module, "main")


# ---------------------------------------------------------------- 架构守卫（ADR-0001 / ADR-0012）


def _import_roots(path: pathlib.Path) -> set[str]:
    """AST 级 import 根名（`import x.y` 记 x），比运行时 import 更接近源码事实。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.architecture
def test_core_never_imports_http_or_apps_layers() -> None:
    files = sorted((REPO_ROOT / "bfgi" / "core").rglob("*.py"))
    assert files, "bfgi/core 目录不应为空"
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(_import_roots(path) & CORE_FORBIDDEN)
        for path in files
        if _import_roots(path) & CORE_FORBIDDEN
    }
    assert offenders == {}


@pytest.mark.architecture
def test_api_layer_imports_stay_inside_allowed_set() -> None:
    files = sorted((REPO_ROOT / "apps").rglob("*.py"))
    assert files, "apps/ 目录不应为空"
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(_import_roots(path) - API_ALLOWED)
        for path in files
        if _import_roots(path) - API_ALLOWED
    }
    assert offenders == {}
