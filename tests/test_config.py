"""SYS-004 冻结测试：配置加载行为与只读边界（ADR-0009）。

冻结的契约：
1. 仓库自带的 `.env.example` 必须能加载成功——它是配置名的权威样例，不允许自相矛盾。
2. 任何**含凭据语义 token** 的变量名一律拒绝，与 token 在名字里的位置无关。
   （旧正则 `(BINANCE|MBX).*(API|KEY|SECRET|TOKEN|PASSPHRASE)` 既误杀
   `BINANCE_FUTURES_API_BASE`（模块自己要求必填的键），又漏检 `API_KEY_BINANCE`。）
3. 任何 `BINANCE` / `MBX` 前缀但不在显式白名单内的配置名一律拒绝（fail-closed）。
4. 拒绝时 `details` 只写变量名，绝不写值。
5. 优先级：显式 dotenv 文件 / 默认候选（`.env` 再 `.env.local` 覆盖）< 运行时 env；
   运行时里的空字符串视为"未设置"，不参与覆盖。
6. 扫描规模按 docs/03 分两档，档位与配置名的对应关系不允许漂移：
   `MAX_MARKET_SYMBOLS_DEEP` = 初筛后的多周期计算档 60–100（硬上限 100，docs/09 样例取 100）；
   `MAX_DERIVATIVES_SYMBOLS` = 精选深数据档 20–30（硬上限 30，ADR-0002 §3 按 30 个估算算力）。
   低于推荐档位 → warning；超过硬上限 → CONFIG_ERROR。
"""

from __future__ import annotations

import json
import pathlib

import pytest

from bfgi.core.config import (
    ALLOWED_MARKET_CONFIG_KEYS,
    load_settings,
    load_settings_from_env,
    parse_dotenv,
)
from bfgi.core.constants import (
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DERIVATIVES_SYMBOLS_HARD_MAX,
    DERIVATIVES_SYMBOLS_RECOMMENDED,
    MARKET_SYMBOLS_MULTITF_HARD_MAX,
    MARKET_SYMBOLS_MULTITF_RECOMMENDED,
    MAX_PLAN_VALID_MINUTES,
)
from bfgi.core.errors import BfgiError, ErrorCode

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# 用于验证"值不会被写进日志/details"的哨兵值，绝不出现在真实配置里。
SENTINEL = "SENTINEL-VALUE-MUST-NOT-BE-LOGGED-4f31"


def base_env(**overrides: str) -> dict[str, str]:
    """以 .env.example 为基线构造配置（不复制常量，避免样例与测试漂移）。"""
    env = parse_dotenv(ENV_EXAMPLE.read_text(encoding="utf-8"))
    env.update(overrides)
    return env


def error_code_of(env: dict[str, str]) -> ErrorCode:
    with pytest.raises(BfgiError) as excinfo:
        load_settings(env)
    return excinfo.value.code


# ---------------------------------------------------------------- 契约 1

def test_env_example_is_loadable() -> None:
    """回归：用仓库自己的样例配置必须能构造出 Settings。"""
    settings = load_settings(parse_dotenv(ENV_EXAMPLE.read_text(encoding="utf-8")))
    assert settings.app_env == "development"
    assert settings.app_tz == "UTC"
    assert settings.binance_futures_api_base == "https://fapi.binance.com"
    assert settings.market_scan_interval_minutes == DEFAULT_SCAN_INTERVAL_MINUTES
    assert settings.futures_only_read_only is True
    assert settings.warnings == ()


def test_env_example_declares_every_required_key() -> None:
    """样例必须覆盖 load_settings 的必填项，否则部署时才会暴露缺口。"""
    keys = set(parse_dotenv(ENV_EXAMPLE.read_text(encoding="utf-8")))
    assert {"BINANCE_FUTURES_API_BASE", "DATABASE_URL", "APP_TZ", "APP_ENV"} <= keys


# ---------------------------------------------------------------- 契约 2

@pytest.mark.parametrize(
    "key",
    [
        "BINANCE_FUTURES_API_KEY",
        "BINANCE_FUTURES_API_SECRET",
        "API_KEY_BINANCE",  # 旧正则的漏检点：凭据 token 出现在 BINANCE 之前
        "MBX_APIKEY",
        "X_MBX_APIKEY",
        "MBX_SECRET",
        "BINANCE_PASSPHRASE",
        "BINANCE_API_PASSWORD",
        "BINANCE_FUTURES_AUTH_TOKEN",
        "AUTH_SECRET",
        "ALERT_WEBHOOK_TOKEN",
        "GRID_CREDENTIAL",
    ],
)
def test_credential_shaped_names_are_rejected(key: str) -> None:
    env = base_env(**{key: SENTINEL})
    with pytest.raises(BfgiError) as excinfo:
        load_settings(env)
    error = excinfo.value
    assert error.code is ErrorCode.READ_ONLY_VIOLATION
    assert key in error.details["keys"]


@pytest.mark.parametrize("key", ["BINANCE_FUTURES_WS_BASE", "BINANCE_BASE_URL", "MBX_API_BASE"])
def test_undeclared_exchange_prefixed_keys_are_rejected(key: str) -> None:
    """交易所前缀必须走白名单：新增配置名要显式声明，不能靠正则碰运气。"""
    assert key not in ALLOWED_MARKET_CONFIG_KEYS
    assert error_code_of(base_env(**{key: SENTINEL})) is ErrorCode.READ_ONLY_VIOLATION


def test_allowlist_itself_contains_no_credential_tokens() -> None:
    """fail-closed 自检：白名单如果被写成含凭据 token，等价于把凭据合法化。"""
    assert ALLOWED_MARKET_CONFIG_KEYS
    leaked = [name for name in ALLOWED_MARKET_CONFIG_KEYS if "API" in name and name not in {"BINANCE_FUTURES_API_BASE"}]
    for name in ALLOWED_MARKET_CONFIG_KEYS:
        upper = name.upper()
        assert not any(token in upper for token in ("KEY", "SECRET", "TOKEN", "PASSPHRASE", "PASSWORD", "CREDENTIAL"))
    assert leaked == []


def test_rejection_does_not_leak_values() -> None:
    """ADR-0009：只记录变量名，绝不记录值。"""
    env = base_env(BINANCE_FUTURES_API_KEY=SENTINEL)
    with pytest.raises(BfgiError) as excinfo:
        load_settings(env)
    payload = json.dumps(excinfo.value.to_dict(), ensure_ascii=False)
    assert SENTINEL not in payload


def test_read_only_flag_cannot_be_turned_off() -> None:
    assert error_code_of(base_env(FUTURES_ONLY_READ_ONLY="false")) is ErrorCode.READ_ONLY_VIOLATION


# ---------------------------------------------------------------- 契约 5

def test_dotenv_file_is_used_when_runtime_env_is_empty(tmp_path: pathlib.Path) -> None:
    dotenv = tmp_path / "custom.env"
    dotenv.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    settings = load_settings_from_env(env={}, dotenv_file=dotenv)
    assert settings.binance_futures_api_base == "https://fapi.binance.com"
    assert settings.max_derivatives_symbols == 30


def test_explicit_missing_dotenv_file_fails_fast(tmp_path: pathlib.Path) -> None:
    """显式声明的配置来源失效必须立刻报错，而不是推迟成"缺少必填配置"。"""
    missing = tmp_path / "absent.env"
    with pytest.raises(BfgiError) as excinfo:
        load_settings_from_env(env={}, dotenv_file=missing)
    assert excinfo.value.code is ErrorCode.CONFIG_ERROR
    assert excinfo.value.details["dotenv_file"] == str(missing)


def test_runtime_env_overrides_dotenv_file(tmp_path: pathlib.Path) -> None:
    dotenv = tmp_path / "custom.env"
    dotenv.write_text("MARKET_SCAN_INTERVAL_MINUTES=20\n", encoding="utf-8")
    # 必填项走 base_env（样例基线）， dotenv 只提供要验证的那一个键；
    # 运行时把该键改成 7 → 断言 7，证明"运行时 > dotenv"，dotenv 的值不可能被当成最终值。
    runtime = base_env(APP_ENV="production", MARKET_SCAN_INTERVAL_MINUTES="7")
    settings = load_settings_from_env(env=runtime, dotenv_file=dotenv)
    assert settings.market_scan_interval_minutes == 7


def test_empty_runtime_value_does_not_shadow_dotenv(tmp_path: pathlib.Path) -> None:
    dotenv = tmp_path / "custom.env"
    dotenv.write_text("MAX_DERIVATIVES_SYMBOLS=25\n", encoding="utf-8")
    # dotenv 写 25，样例基线是 30，运行时是容器常见的 `VAR=` 空值：
    # 断言 25 同时排掉两种错法——把空串当值（→ 报错/0）与忽略 dotenv（→ 30）。
    runtime = base_env(APP_ENV="production", MAX_DERIVATIVES_SYMBOLS="")
    settings = load_settings_from_env(env=runtime, dotenv_file=dotenv)
    assert settings.max_derivatives_symbols == 25


def test_default_candidates_local_overrides_base(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """.env 提供基线，.env.local 覆盖同名键（本地/部署差异的约定）。"""
    (tmp_path / ".env").write_text(
        "MAX_DERIVATIVES_SYMBOLS=30\nDEFAULT_PLAN_VALID_MINUTES=240\n", encoding="utf-8"
    )
    (tmp_path / ".env.local").write_text("MAX_DERIVATIVES_SYMBOLS=25\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # 从运行时里撤掉这两个键，让它们只能来自 .env / .env.local：
    # 如果默认候选没被读取，就会直接"缺少必填配置"，测试失败——不会因为基线里恰好有同名默认值而蒙混过关。
    runtime = base_env(APP_ENV="production")
    runtime.pop("MAX_DERIVATIVES_SYMBOLS")
    runtime.pop("DEFAULT_PLAN_VALID_MINUTES")
    settings = load_settings_from_env(env=runtime)
    assert settings.max_derivatives_symbols == 25
    assert settings.default_plan_valid_minutes == 240


def test_credentials_in_dotenv_file_are_rejected(tmp_path: pathlib.Path) -> None:
    """凭据扫描必须覆盖 dotenv 来源，不只是 os.environ。"""
    dotenv = tmp_path / "custom.env"
    dotenv.write_text(f"BINANCE_FUTURES_API_KEY={SENTINEL}\n", encoding="utf-8")
    with pytest.raises(BfgiError) as excinfo:
        load_settings_from_env(env={}, dotenv_file=dotenv)
    assert excinfo.value.code is ErrorCode.READ_ONLY_VIOLATION
    assert SENTINEL not in json.dumps(excinfo.value.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------- 既有不变量（回归）

def test_app_tz_must_be_utc() -> None:
    assert error_code_of(base_env(APP_TZ="Asia/Shanghai")) is ErrorCode.CONFIG_ERROR


def test_http_base_is_allowed_only_in_development() -> None:
    assert error_code_of(base_env(APP_ENV="production", BINANCE_FUTURES_API_BASE="http://localhost:8080")) is ErrorCode.CONFIG_ERROR
    settings = load_settings(base_env(APP_ENV="development", BINANCE_FUTURES_API_BASE="http://127.0.0.1:8080"))
    assert settings.binance_futures_api_base == "http://127.0.0.1:8080"


def test_non_allowlisted_https_host_is_rejected() -> None:
    assert error_code_of(base_env(BINANCE_FUTURES_API_BASE="https://fapi.binance.ru")) is ErrorCode.CONFIG_ERROR


def test_database_url_must_be_sqlite() -> None:
    assert error_code_of(base_env(DATABASE_URL="postgresql://user@host/db")) is ErrorCode.CONFIG_ERROR


def test_plan_valid_minutes_above_cap_is_rejected() -> None:
    assert error_code_of(base_env(DEFAULT_PLAN_VALID_MINUTES=str(MAX_PLAN_VALID_MINUTES + 1))) is ErrorCode.CONFIG_ERROR


def test_missing_required_key_is_reported_as_config_error() -> None:
    env = base_env()
    env.pop("DATABASE_URL")
    assert error_code_of(env) is ErrorCode.CONFIG_ERROR


def test_scan_interval_drift_produces_warning_not_error() -> None:
    settings = load_settings(base_env(MARKET_SCAN_INTERVAL_MINUTES="20"))
    assert settings.market_scan_interval_minutes == 20
    assert settings.warnings


# ---------------------------------------------------------------- 契约 6

def test_sample_configuration_satisfies_both_scan_bands() -> None:
    """回归（SYS-004 复测发现）：旧实现把 docs/03"精选 20–30"错挂到 MAX_MARKET_SYMBOLS_DEEP 上，
    于是仓库自带样例（docs/09 的 MAX_MARKET_SYMBOLS_DEEP=100）一加载就报 warning——
    权威样例与校验互相矛盾。档位对应关系修正后，样例必须干净加载。
    """
    settings = load_settings(base_env(MAX_MARKET_SYMBOLS_DEEP="100", MAX_DERIVATIVES_SYMBOLS="30"))
    assert settings.max_market_symbols_deep == 100
    assert settings.max_derivatives_symbols == 30
    assert settings.warnings == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MAX_MARKET_SYMBOLS_DEEP", "40"),  # 低于多周期档 60–100，但仍是合法配置
        ("MAX_DERIVATIVES_SYMBOLS", "10"),  # 低于精选档 20–30
    ],
)
def test_below_recommended_scan_band_is_warning_not_error(key: str, value: str) -> None:
    settings = load_settings(base_env(**{key: value}))
    assert any(key in message for message in settings.warnings), settings.warnings


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MAX_MARKET_SYMBOLS_DEEP", "101"),  # 超过多周期硬上限 100
        ("MAX_DERIVATIVES_SYMBOLS", "31"),  # 超过深数据硬上限 30（ADR-0002 算力上限）
    ],
)
def test_above_hard_scan_cap_is_config_error(key: str, value: str) -> None:
    assert error_code_of(base_env(**{key: value})) is ErrorCode.CONFIG_ERROR


def test_scan_band_constants_match_docs() -> None:
    """档位数字集中定义在 constants.py（禁止散落魔法数字），这里锁住与 docs/03 / ADR-0002 的对应。"""
    assert MARKET_SYMBOLS_MULTITF_RECOMMENDED == (60, 100)
    assert MARKET_SYMBOLS_MULTITF_HARD_MAX == 100
    assert DERIVATIVES_SYMBOLS_RECOMMENDED == (20, 30)
    assert DERIVATIVES_SYMBOLS_HARD_MAX == 30
    assert DERIVATIVES_SYMBOLS_HARD_MAX <= MARKET_SYMBOLS_MULTITF_RECOMMENDED[0]
