import pytest

import kv.main
from kv.main import build_app


def test_role_selects_app(tmp_path):
    env = {"KV_ROLE": "coordinator", "KV_MODE": "single", "KV_CATALOG_PATH": str(tmp_path / "c")}
    coordinator_paths = {r.path for r in build_app(env).routes}
    shard_paths = {r.path for r in build_app({"KV_ROLE": "shard"}).routes}
    assert "/tables" in coordinator_paths
    assert "/internal/items/{table}/{pk:path}" in shard_paths


def test_missing_role_rejected():
    with pytest.raises(ValueError):
        build_app({})


def test_app_attribute_is_cached(monkeypatch, tmp_path):
    monkeypatch.setenv("KV_ROLE", "shard")
    kv.main._cached_app.cache_clear()
    assert kv.main.app is kv.main.app
    kv.main._cached_app.cache_clear()
