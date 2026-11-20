import pytest
from fastapi.testclient import TestClient

from kv.coordinator.app import create_coordinator_app
from kv.coordinator.registry import ShardRegistry
from kv.ring import EmptyRingError, HashRing
from kv.settings import Settings

SHARD_A = "s1"
SHARD_B = "s2"
URL_OLD = "http://s1:8000"
URL_NEW = "http://s1-new:8000"
KEY_COUNT = 1_000
KEYS = [f"key-{i}" for i in range(KEY_COUNT)]
BAD_URLS = ["", "s1:8000", "ftp://s1", "http://", "not a url", "http://[", "http://:80"]


@pytest.fixture
def registry():
    return ShardRegistry(HashRing())


def test_register_new_created(registry):
    assert registry.register(SHARD_A, URL_OLD) == "created"


def test_same_id_same_url_unchanged(registry):
    registry.register(SHARD_A, URL_OLD)
    assert registry.register(SHARD_A, URL_OLD) == "unchanged"


def test_same_id_new_url_updates_url_keeps_placement(registry):
    registry.register(SHARD_A, URL_OLD)
    registry.register(SHARD_B, "http://s2:8000")
    before = [registry.owner_for_key(k)[0] for k in KEYS]
    assert registry.register(SHARD_A, URL_NEW) == "updated"
    assert [registry.owner_for_key(k)[0] for k in KEYS] == before
    assert (SHARD_A, URL_NEW) in registry.list()


def test_remove_unknown_noop(registry):
    registry.remove("ghost")
    assert registry.list() == []


def test_remove_then_empty_ring(registry):
    registry.register(SHARD_A, URL_OLD)
    registry.remove(SHARD_A)
    with pytest.raises(EmptyRingError):
        registry.owner_for_key("k")


def test_owner_for_key_returns_id_and_url(registry):
    registry.register(SHARD_A, URL_OLD)
    assert registry.owner_for_key("k") == (SHARD_A, URL_OLD)


def test_list_sorted_by_id(registry):
    registry.register(SHARD_B, "http://s2:8000")
    registry.register(SHARD_A, URL_OLD)
    assert [i for i, _ in registry.list()] == [SHARD_A, SHARD_B]


@pytest.fixture(params=["single", "sharded"])
def api(request, tmp_path):
    settings = Settings(role="coordinator", mode=request.param, catalog_path=tmp_path / "c.json")
    return TestClient(create_coordinator_app(settings, backend=_NoBackend()))


class _NoBackend:
    pass


def test_api_register_list_delete_health(api):
    body = {"id": SHARD_A, "url": URL_OLD}
    assert api.post("/shards", json=body).status_code == 201
    assert api.post("/shards", json=body).status_code == 200
    assert api.post("/shards", json={**body, "url": URL_NEW}).status_code == 200
    assert api.get("/shards").json() == [{"id": SHARD_A, "url": URL_NEW}]
    assert api.get("/health").json()["shards"] == 1
    assert api.delete(f"/shards/{SHARD_A}").status_code == 204
    assert api.delete(f"/shards/{SHARD_A}").status_code == 204
    assert api.get("/shards").json() == []
    assert api.get("/health").json()["shards"] == 0


@pytest.mark.parametrize("url", BAD_URLS)
def test_api_rejects_bad_url(api, url):
    response = api.post("/shards", json={"id": SHARD_A, "url": url})
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_api_rejects_empty_id(api):
    assert api.post("/shards", json={"id": "", "url": URL_OLD}).status_code == 400


def test_injected_registry_backs_shards_and_health(tmp_path):
    injected = ShardRegistry(HashRing())
    injected.register(SHARD_A, URL_OLD)
    settings = Settings(role="coordinator", mode="single", catalog_path=tmp_path / "c.json")
    app = create_coordinator_app(settings, registry=injected)
    client = TestClient(app)
    assert app.state.registry is injected
    assert client.get("/shards").json() == [{"id": SHARD_A, "url": URL_OLD}]
    assert client.get("/health").json()["shards"] == 1
