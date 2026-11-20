import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

Role = Literal["coordinator", "shard"]
Mode = Literal["single", "sharded"]

ENV_PREFIX = "KV_"
# ADR-0006: virtual nodes per shard on the hash ring.
DEFAULT_VNODES = 200
DEFAULT_MODE: Mode = "sharded"
DEFAULT_CATALOG_PATH = Path("/data/catalog.json")
DEFAULT_HEARTBEAT_S = 15.0
DEFAULT_CONNECT_TIMEOUT_S = 0.5
DEFAULT_READ_TIMEOUT_S = 2.0


@dataclass(frozen=True)
class Settings:
    role: Role
    mode: Mode = DEFAULT_MODE
    shard_id: str | None = None
    advertise_url: str | None = None
    coordinator_url: str | None = None
    catalog_path: Path = DEFAULT_CATALOG_PATH
    vnodes: int = DEFAULT_VNODES
    heartbeat_s: float = DEFAULT_HEARTBEAT_S
    connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S
    read_timeout_s: float = DEFAULT_READ_TIMEOUT_S


def _choice(
    env: Mapping[str, str], name: str, allowed: tuple[str, ...], default: str | None
) -> str:
    value = env.get(ENV_PREFIX + name, default)
    if value not in allowed:
        raise ValueError(f"{ENV_PREFIX}{name} must be one of {allowed}, got {value!r}")
    return value


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    def opt(name: str, cast=str, default=None):
        raw = env.get(ENV_PREFIX + name)
        return default if raw is None else cast(raw)

    return Settings(
        role=_choice(env, "ROLE", get_args(Role), None),
        mode=_choice(env, "MODE", get_args(Mode), DEFAULT_MODE),
        shard_id=opt("SHARD_ID"),
        advertise_url=opt("ADVERTISE_URL"),
        coordinator_url=opt("COORDINATOR_URL"),
        catalog_path=opt("CATALOG_PATH", Path, DEFAULT_CATALOG_PATH),
        vnodes=opt("VNODES", int, DEFAULT_VNODES),
        heartbeat_s=opt("HEARTBEAT_S", float, DEFAULT_HEARTBEAT_S),
        connect_timeout_s=opt("CONNECT_TIMEOUT_S", float, DEFAULT_CONNECT_TIMEOUT_S),
        read_timeout_s=opt("READ_TIMEOUT_S", float, DEFAULT_READ_TIMEOUT_S),
    )
