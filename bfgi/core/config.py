"""配置加载与校验（SYS-002 / SYS-004）。

字段与仓库根 `.env.example` 一一对应；**不存在任何交易所凭据字段**（ADR-0009）：
本模块只接受公共行情基址，遇到疑似交易所 API key/secret 的环境变量直接报错而不是忽略。

设计约束：
- `load_settings(env)` 是纯函数，不读文件、不读 `os.environ`，便于单测与回放一致性（AGENTS.md §7）。
- 校验失败一律 `BfgiError(CONFIG_ERROR)`，把"配置漂移"在入口挡住，而不是让下游用默认值继续跑。
- 超出"推荐区间"但不违反硬阈值的取值 → `Settings.warnings`，由 worker/API 决定是否上报（不静默、也不误报错）。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from bfgi.core.constants import (
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DERIVATIVES_SYMBOLS_HARD_MAX,
    DERIVATIVES_SYMBOLS_RECOMMENDED,
    MARKET_REQUEST_CONCURRENCY_HARD_MAX,
    MARKET_REQUEST_CONCURRENCY_RECOMMENDED,
    MARKET_SYMBOLS_MULTITF_HARD_MAX,
    MARKET_SYMBOLS_MULTITF_RECOMMENDED,
    MAX_PLAN_VALID_MINUTES,
)
from bfgi.core.errors import BfgiError, ErrorCode

APP_ENV_VALUES = ("development", "test", "staging", "production")

# docs/03 的行情端点全部在 Binance USDⓈ-M 公共 REST 主机上；固定主机名可防止把采集指向任意主机。
# 本地/测试需要 http 时只允许回环地址，且必须是 development（见 _validate_api_base）。
ALLOWED_API_HOSTS = frozenset({"fapi.binance.com"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# ADR-0009：只读是架构不变量。凭据类变量名一旦出现就报错（details 只写变量名，绝不写值）。
# 两条规则彼此独立。旧实现只有一条 `(BINANCE|MBX).*(API|KEY|SECRET|TOKEN|PASSPHRASE)`，
# 同时犯了两个错：
#   1. 误杀自己必填的 `BINANCE_FUTURES_API_BASE`（用仓库自带 .env.example 必然 READ_ONLY_VIOLATION）；
#   2. 漏检凭据 token 出现在 BINANCE 之前的名字（`API_KEY_BINANCE`、`X_MBX_APIKEY`）。
# 规则一：凭据 token 出现在名字任意位置都拒绝（与顺序无关）。
_CREDENTIAL_TOKEN_PATTERN = re.compile(r"(KEY|SECRET|TOKEN|PASSPHRASE|PASSWORD|CREDENTIAL|AUTH)", re.IGNORECASE)
# 规则二：交易所前缀的配置名必须显式声明在下面的白名单里，未声明一律拒绝（fail-closed）。
_EXCHANGE_PREFIX_PATTERN = re.compile(r"^(BINANCE|MBX)")

# 只读系统允许的交易所相关配置名：只有公共行情基址（docs/03 全部是公共端点）。
# 新增这个名字里的任何项都要经过代码评审——它等价于扩大只读边界。
ALLOWED_MARKET_CONFIG_KEYS: frozenset[str] = frozenset({"BINANCE_FUTURES_API_BASE"})

_TRUE_WORDS = frozenset({"1", "true", "yes", "on"})
_FALSE_WORDS = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class Settings:
    """运行时配置。字段与 `.env.example` 对齐；新增字段必须同步 `.env.example`（SYS-005）。"""

    app_env: str
    app_tz: str
    binance_futures_api_base: str
    market_scan_interval_minutes: int
    max_concurrent_market_requests: int
    max_market_symbols_deep: int
    max_derivatives_symbols: int
    futures_only_read_only: bool
    default_plan_valid_minutes: int
    database_url: str
    app_public_url: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def parse_dotenv(text: str) -> dict[str, str]:
    """解析 `.env` 文本（不支持多行值）。空行与 `#` 注释忽略；缺少 `=` 视为配置错误。"""
    result: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            raise BfgiError(ErrorCode.CONFIG_ERROR, f".env 第 {lineno} 行缺少 '='", {"lineno": lineno})
        key = key.strip()
        if not key:
            raise BfgiError(ErrorCode.CONFIG_ERROR, f".env 第 {lineno} 行变量名为空", {"lineno": lineno})
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[key] = value
    return result


def load_settings(env: Mapping[str, str]) -> Settings:
    """校验并构造 Settings。`env` 是纯输入（测试传 dict，进程传 `os.environ`）。"""
    _reject_credential_keys(env)

    warnings: list[str] = []

    app_env = _required(env, "APP_ENV").lower()
    if app_env not in APP_ENV_VALUES:
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"APP_ENV 必须是 {APP_ENV_VALUES} 之一", {"APP_ENV": app_env})

    # AGENTS.md §7：全部时间 UTC。允许本地时区会让回放与实时产生不同结果。
    app_tz = _required(env, "APP_TZ").upper()
    if app_tz != "UTC":
        raise BfgiError(ErrorCode.CONFIG_ERROR, "APP_TZ 必须是 UTC（所有时间 UTC，回放=实时）", {"APP_TZ": app_tz})

    api_base = _validate_api_base(_required(env, "BINANCE_FUTURES_API_BASE"), app_env)

    scan_interval = _int(env, "MARKET_SCAN_INTERVAL_MINUTES", low=1, high=1440)
    if scan_interval != DEFAULT_SCAN_INTERVAL_MINUTES:
        warnings.append(f"MARKET_SCAN_INTERVAL_MINUTES={scan_interval} 偏离默认 15 分钟 slot（ADR-0003）")
    if 60 % scan_interval != 0:
        warnings.append(f"MARKET_SCAN_INTERVAL_MINUTES={scan_interval} 不是 60 的约数，slot 对齐会跨小时漂移")

    concurrency = _int(env, "MAX_CONCURRENT_MARKET_REQUESTS", low=1, high=MARKET_REQUEST_CONCURRENCY_HARD_MAX)
    lo, hi = MARKET_REQUEST_CONCURRENCY_RECOMMENDED
    if not lo <= concurrency <= hi:
        warnings.append(f"MAX_CONCURRENT_MARKET_REQUESTS={concurrency} 超出推荐区间 {lo}-{hi}（docs/02 §6）")

    # docs/03 分两档：初筛后 60–100 个标的做多周期计算（MAX_MARKET_SYMBOLS_DEEP）；
    # 精选 20–30 个请求较贵的 OI/主动成交/深度数据（MAX_DERIVATIVES_SYMBOLS，ADR-0002 §3 也按 30 个估算算力）。
    # 旧实现把 20–30 这一档错挂到 MAX_MARKET_SYMBOLS_DEEP 上，于是仓库自带 .env.example（=100，docs/09）
    # 一加载就产生 warning——样例配置与校验互相矛盾（SYS-004 复测发现）。
    market_symbols = _int(env, "MAX_MARKET_SYMBOLS_DEEP", low=1, high=MARKET_SYMBOLS_MULTITF_HARD_MAX)
    if market_symbols < MARKET_SYMBOLS_MULTITF_RECOMMENDED[0]:
        warnings.append(
            f"MAX_MARKET_SYMBOLS_DEEP={market_symbols} 低于 docs/03 多周期计算推荐档位 "
            f"{MARKET_SYMBOLS_MULTITF_RECOMMENDED[0]}–{MARKET_SYMBOLS_MULTITF_RECOMMENDED[1]}"
        )

    derivatives = _int(env, "MAX_DERIVATIVES_SYMBOLS", low=1, high=DERIVATIVES_SYMBOLS_HARD_MAX)
    if derivatives < DERIVATIVES_SYMBOLS_RECOMMENDED[0]:
        warnings.append(
            f"MAX_DERIVATIVES_SYMBOLS={derivatives} 低于 docs/03 精选深数据推荐档位 "
            f"{DERIVATIVES_SYMBOLS_RECOMMENDED[0]}–{DERIVATIVES_SYMBOLS_RECOMMENDED[1]}"
        )

    # ADR-0009：不提供"开启交易"的开关。写成 false 不是配置错误，而是越界请求。
    read_only = _bool(env, "FUTURES_ONLY_READ_ONLY")
    if not read_only:
        raise BfgiError(
            ErrorCode.READ_ONLY_VIOLATION,
            "FUTURES_ONLY_READ_ONLY 必须为 true：只读是架构不变量（AGENTS.md §6 / ADR-0009），系统不提供交易开关",
        )

    # docs/04：valid_until <= as_of + 4h。配置层不允许放宽到 4h 以上（更严格的边界优先）。
    plan_valid = _int(env, "DEFAULT_PLAN_VALID_MINUTES", low=1, high=MAX_PLAN_VALID_MINUTES)

    database_url = _validate_database_url(_required(env, "DATABASE_URL"))
    public_url = _validate_public_url(_required(env, "APP_PUBLIC_URL"))

    return Settings(
        app_env=app_env,
        app_tz=app_tz,
        binance_futures_api_base=api_base,
        market_scan_interval_minutes=scan_interval,
        max_concurrent_market_requests=concurrency,
        max_market_symbols_deep=market_symbols,
        max_derivatives_symbols=derivatives,
        futures_only_read_only=True,
        default_plan_valid_minutes=plan_valid,
        database_url=database_url,
        app_public_url=public_url,
        warnings=tuple(warnings),
    )


# 默认配置文件候选，按优先级从低到高排列。`.env.local` 只用于本地覆盖，同样不允许含凭据。
ENV_FILE_CANDIDATES: tuple[str, ...] = (".env", ".env.local")


def load_settings_from_env(
    env: Mapping[str, str] | None = None,
    dotenv_file: str | Path | None = None,
) -> Settings:
    """进程入口：`.env` 提供非敏感基线，真实环境变量优先覆盖它。

    优先级（低 → 高）：默认候选 `.env` → `.env.local` → 显式 `dotenv_file` → 运行时 env。
    - 默认候选按 `ENV_FILE_CANDIDATES` 顺序读取，后读到的同名键覆盖前者；
    - 显式指定 `dotenv_file` 表示调用方声明了配置来源，文件不存在必须报错而不是静默跳过
      （docs/09 要求发布带配置样例，静默忽略会把配置错误推迟成运行期故障）；
    - 运行时 env 里的空字符串视为"未设置"，不参与覆盖（容器里常见 `VAR=`）。

    secrets 不从这里进入（ADR-0009 / docs/09：sensitive token 只放私有 secrets store）。
    """
    base: dict[str, str] = {}
    if dotenv_file is not None:
        _merge_dotenv(Path(dotenv_file), base, required=True)
    else:
        for candidate in ENV_FILE_CANDIDATES:
            _merge_dotenv(Path(candidate), base, required=False)
    runtime = {} if env is None else dict(env)
    base.update({key: value for key, value in runtime.items() if value != ""})
    return load_settings(base)


def _merge_dotenv(path: Path, target: dict[str, str], *, required: bool) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if required:
            raise BfgiError(
                ErrorCode.CONFIG_ERROR,
                f"指定的配置文件不存在：{path}",
                {"dotenv_file": str(path)},  # 只记录路径，不记录内容
            ) from None
        return
    except OSError as exc:
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"配置文件读取失败：{path.name}", {"reason": type(exc).__name__}) from exc
    target.update(parse_dotenv(text))


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"缺少必填配置 {key}（见 .env.example）", {"key": key})
    return value


def _reject_credential_keys(env: Mapping[str, str]) -> None:
    """出现疑似凭据变量名或未声明的交易所配置名就终止：这是只读边界的一部分（ADR-0009）。"""
    offenders = sorted(
        key
        for key in env
        if _CREDENTIAL_TOKEN_PATTERN.search(key)
        or (_EXCHANGE_PREFIX_PATTERN.match(key) and key not in ALLOWED_MARKET_CONFIG_KEYS)
    )
    if offenders:
        raise BfgiError(
            ErrorCode.READ_ONLY_VIOLATION,
            "检测到疑似交易所凭据环境变量，本系统只使用公共行情端点，不接受交易凭据（ADR-0009）",
            {"keys": offenders},  # 只记录变量名，绝不记录值
        )


def _int(env: Mapping[str, str], key: str, *, low: int, high: int) -> int:
    raw = _required(env, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"{key} 必须是整数", {"key": key, "value": raw}) from exc
    if not low <= value <= high:
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"{key} 必须在 {low}–{high} 之间", {"key": key, "value": value})
    return value


def _bool(env: Mapping[str, str], key: str) -> bool:
    raw = _required(env, key).lower()
    if raw in _TRUE_WORDS:
        return True
    if raw in _FALSE_WORDS:
        return False
    raise BfgiError(ErrorCode.CONFIG_ERROR, f"{key} 必须是布尔字面量（true/false）", {"key": key, "value": raw})


def _validate_api_base(raw: str, app_env: str) -> str:
    parts = urlsplit(raw)
    if parts.scheme not in {"https", "http"} or not parts.netloc:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "BINANCE_FUTURES_API_BASE 必须是绝对 http/https URL", {"key": "BINANCE_FUTURES_API_BASE"})
    if parts.username or parts.password:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "BINANCE_FUTURES_API_BASE 不允许包含用户名/密码")
    if parts.query or parts.fragment:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "BINANCE_FUTURES_API_BASE 不允许包含 query/fragment")
    host = parts.hostname or ""
    if parts.scheme == "http":
        # 只有开发环境的回环地址可以走明文（本地 mock/代理），生产环境一律 https。
        if host not in LOOPBACK_HOSTS or app_env != "development":
            raise BfgiError(ErrorCode.CONFIG_ERROR, "BINANCE_FUTURES_API_BASE 在非开发环境必须使用 https 或已知主机")
    elif host not in ALLOWED_API_HOSTS:
        raise BfgiError(
            ErrorCode.CONFIG_ERROR,
            f"BINANCE_FUTURES_API_BASE 主机 {host!r} 不在允许列表 {sorted(ALLOWED_API_HOSTS)}",
        )
    if parts.path not in {"", "/"}:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "BINANCE_FUTURES_API_BASE 不应包含路径（路径由 market_data 层拼接）")
    return f"{parts.scheme}://{parts.netloc}"


def _validate_database_url(raw: str) -> str:
    # ADR-0010：M0/M1 使用 SQLite(WAL)。Postgres 接口在 DEP-003 引入，届时同步放宽并新增 ADR。
    if not raw.startswith("sqlite"):
        raise BfgiError(ErrorCode.CONFIG_ERROR, "DATABASE_URL 目前只支持 sqlite（Postgres 见 DEP-003）", {"value_scheme": raw.split(":", 1)[0]})
    return raw


def _validate_public_url(raw: str) -> str:
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "APP_PUBLIC_URL 必须是绝对 http/https URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise BfgiError(ErrorCode.CONFIG_ERROR, "APP_PUBLIC_URL 不允许包含凭据/query/fragment")
    return raw
