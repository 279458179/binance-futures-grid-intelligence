"""版本身份三元组与血缘字段（ADR-0011）。

`git_commit` 由构建/运行环境注入（CI 写 `BFGI_GIT_COMMIT=${{ github.sha }}`），**不在源码里硬编码**；
`market_data_hash` 由 `bfgi/core/hashing.py` 计算。缺失就必须报错，而不是给一个"看起来能用"的默认值。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from bfgi.core.constants import SCHEMA_VERSION
from bfgi.core.errors import BfgiError, ErrorCode

# 策略语义版本：与 pyproject.toml 的 version 保持一致（tests/unit/test_version.py 有断言）。
STRATEGY_VERSION = "0.1.0"

GIT_COMMIT_ENV = "BFGI_GIT_COMMIT"
IMAGE_DIGEST_ENV = "BFGI_IMAGE_DIGEST"

# 允许 7–40 位十六进制：git 短 SHA 到完整 SHA。空值/非 SHA 一律拒绝（ADR-0011 可复核性）。
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class VersionIdentity:
    """每条 scan/decision/plan/backtest 记录都必须携带的身份（ADR-0011 §1）。"""

    strategy_version: str
    git_commit: str
    market_data_hash: str
    schema_version: str = SCHEMA_VERSION
    image_digest: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "strategy_version": self.strategy_version,
            "git_commit": self.git_commit,
            "market_data_hash": self.market_data_hash,
            "schema_version": self.schema_version,
            "image_digest": self.image_digest,
        }


def resolve_git_commit(env: Mapping[str, str]) -> str:
    """从环境读取 git commit。缺失或不合法 → CONFIG_ERROR（不允许"未知版本"的报告）。"""
    raw = env.get(GIT_COMMIT_ENV, "").strip()
    if not raw:
        raise BfgiError(
            ErrorCode.CONFIG_ERROR,
            f"缺少 {GIT_COMMIT_ENV}：报告与回测必须绑定 git commit（ADR-0011）。本地运行请设置 BFGI_GIT_COMMIT=$(git rev-parse HEAD)",
        )
    lowered = raw.lower()
    if not _SHA_RE.match(lowered):
        raise BfgiError(ErrorCode.CONFIG_ERROR, f"{GIT_COMMIT_ENV} 不是合法 git SHA", {"value_len": len(raw)})
    return lowered


def build_version_identity(
    env: Mapping[str, str],
    market_data_hash: str,
    schema_version: str = SCHEMA_VERSION,
) -> VersionIdentity:
    """组装版本身份。`market_data_hash` 必须是 64 位十六进制（sha256）。"""
    if not re.fullmatch(r"[0-9a-f]{64}", market_data_hash):
        raise BfgiError(ErrorCode.INVALID_VALUE, "market_data_hash 必须是 64 位十六进制 sha256")
    digest = env.get(IMAGE_DIGEST_ENV, "").strip() or None
    return VersionIdentity(
        strategy_version=STRATEGY_VERSION,
        git_commit=resolve_git_commit(env),
        market_data_hash=market_data_hash,
        schema_version=schema_version,
        image_digest=digest,
    )
