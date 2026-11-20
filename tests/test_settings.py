import pytest

from kv.settings import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_CONNECT_TIMEOUT_S,
    DEFAULT_HEARTBEAT_S,
    DEFAULT_MODE,
    DEFAULT_READ_TIMEOUT_S,
    DEFAULT_VNODES,
    load_settings,
)

CUSTOM_VNODES = 64
CUSTOM_READ_TIMEOUT_S = 3.5


def test_defaults_when_only_role_set():
    s = load_settings({"KV_ROLE": "shard"})
    assert s.role == "shard"
    assert s.mode == DEFAULT_MODE
    assert s.shard_id is None
    assert s.catalog_path == DEFAULT_CATALOG_PATH
    assert s.vnodes == DEFAULT_VNODES
    assert s.heartbeat_s == DEFAULT_HEARTBEAT_S
    assert s.connect_timeout_s == DEFAULT_CONNECT_TIMEOUT_S
    assert s.read_timeout_s == DEFAULT_READ_TIMEOUT_S


def test_missing_role_raises():
    with pytest.raises(ValueError, match="KV_ROLE"):
        load_settings({})


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="KV_MODE"):
        load_settings({"KV_ROLE": "shard", "KV_MODE": "bogus"})


def test_numeric_env_parsed():
    s = load_settings(
        {
            "KV_ROLE": "coordinator",
            "KV_VNODES": str(CUSTOM_VNODES),
            "KV_READ_TIMEOUT_S": str(CUSTOM_READ_TIMEOUT_S),
        }
    )
    assert s.vnodes == CUSTOM_VNODES
    assert s.read_timeout_s == CUSTOM_READ_TIMEOUT_S
