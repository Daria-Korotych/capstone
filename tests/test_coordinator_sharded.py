from urllib.parse import quote

import httpx
import pytest
from fastapi.testclient import TestClient

from kv.coordinator.app import create_coordinator_app
from kv.coordinator.registry import ShardRegistry
from kv.coordinator.sharded import ShardedBackend
from kv.ring import HashRing
from kv.settings import DEFAULT_VNODES, Settings
from kv.shard.app import create_shard_app

SHARD_URLS = {"shard-1": "http://shard-1:8081", "shard-2": "http://shard-2:8081"}
TABLE = "users"
USERS = {"name": TABLE, "partition_key": "user_id"}
KEY_COUNT = 1000
MIN_ITEMS_PER_SHARD = 400
MAX_ITEMS_PER_SHARD = 600
SPECIAL_PK = "a/b?c#d %25 ключ"
ITEM_BODY = {"name": "A"}
CATALOG_FILE = "c.json"
RING_KEY_SEPARATOR = "\x1f"
SHARD_ERROR_STATUS = 502
NO_SHARDS = {"error": "no_shards"}
NO_SHARDS_STATUS = 503
EVENTS_TABLE = "events"
EVENTS = {"name": EVENTS_TABLE, "partition_key": "user_id", "sort_key": "ts"}
EVENT_PK = "u1"
SORT_KEYS = ("t1", "t2")
EVENTS_URL = f"/tables/{EVENTS_TABLE}/items/{EVENT_PK}"


def shard_apps() -> dict[str, httpx.ASGITransport]:
    return {
        sid: httpx.ASGITransport(app=create_shard_app(Settings(role="shard", shard_id=sid)))
        for sid in SHARD_URLS
    }


class Cluster:
    def __init__(self, tmp_path, transports=None, order=tuple(SHARD_URLS)):
        self.transports = transports or shard_apps()
        mounts = {SHARD_URLS[sid]: t for sid, t in self.transports.items()}
        self.shards = httpx.AsyncClient(mounts=mounts)
        self.registry = ShardRegistry(HashRing(DEFAULT_VNODES))
        for sid in order:
            self.registry.register(sid, SHARD_URLS[sid])
        settings = Settings(role="coordinator", catalog_path=tmp_path / CATALOG_FILE)
        app = create_coordinator_app(
            settings, backend=ShardedBackend(self.registry, self.shards), registry=self.registry
        )
        self.api = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://coordinator"
        )

    async def aclose(self) -> None:
        await self.api.aclose()
        await self.shards.aclose()

    async def shard_items(self, sid: str) -> int:
        async with httpx.AsyncClient(
            transport=self.transports[sid], base_url=SHARD_URLS[sid]
        ) as shard:
            return (await shard.get("/health")).json()["items"]


@pytest.fixture
async def cluster(tmp_path):
    c = Cluster(tmp_path)
    assert (await c.api.post("/tables", json=USERS)).status_code == 201
    yield c
    await c.aclose()


def item_url(pk: str) -> str:
    return f"/tables/{TABLE}/items/{quote(pk, safe='')}"


async def test_writes_spread_over_both_shards(cluster):
    for i in range(KEY_COUNT):
        assert (await cluster.api.put(item_url(f"u{i}"), json=ITEM_BODY)).status_code == 201
    for sid in SHARD_URLS:
        assert MIN_ITEMS_PER_SHARD <= await cluster.shard_items(sid) <= MAX_ITEMS_PER_SHARD


async def test_read_goes_to_owner(cluster):
    pk = "u1"
    assert (await cluster.api.put(item_url(pk), json=ITEM_BODY)).status_code == 201
    owner, _ = cluster.registry.owner_for_key(f"{TABLE}{RING_KEY_SEPARATOR}{pk}")
    counts = {sid: await cluster.shard_items(sid) for sid in SHARD_URLS}
    assert counts == {sid: int(sid == owner) for sid in SHARD_URLS}
    assert (await cluster.api.get(item_url(pk))).json() == {"user_id": pk, **ITEM_BODY}
    assert (await cluster.api.head(item_url(pk))).status_code == 200
    assert (await cluster.api.delete(item_url(pk))).status_code == 204
    assert (await cluster.api.get(item_url(pk))).status_code == 404


async def test_no_shards_503(cluster):
    for sid in SHARD_URLS:
        cluster.registry.remove(sid)
    response = await cluster.api.get(item_url("u1"))
    assert response.status_code == NO_SHARDS_STATUS
    assert response.json() == NO_SHARDS


class Raising(httpx.AsyncBaseTransport):
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def handle_async_request(self, request):
        raise self.exc


class Status(httpx.AsyncBaseTransport):
    def __init__(self, status: int) -> None:
        self.status = status

    async def handle_async_request(self, request):
        return httpx.Response(self.status)


@pytest.mark.parametrize(
    "transport",
    [
        Raising(httpx.ConnectTimeout("connect")),
        Raising(httpx.ReadTimeout("read")),
        Raising(httpx.ConnectError("refused")),
        Status(500),
        Status(400),
    ],
    ids=["connect-timeout", "read-timeout", "refused", "shard-5xx", "shard-4xx"],
)
async def test_shard_unreachable_502(tmp_path, transport):
    c = Cluster(tmp_path, transports={sid: transport for sid in SHARD_URLS})
    await c.api.post("/tables", json=USERS)
    owner, _ = c.registry.owner_for_key(f"{TABLE}{RING_KEY_SEPARATOR}u1")
    response = await c.api.get(item_url("u1"))
    assert response.status_code == SHARD_ERROR_STATUS
    assert response.json() == {"error": "shard_unavailable", "shard": owner}
    await c.aclose()


async def test_pk_special_chars_roundtrip_through_coordinator(cluster):
    assert (await cluster.api.put(item_url(SPECIAL_PK), json=ITEM_BODY)).status_code == 201
    response = await cluster.api.get(item_url(SPECIAL_PK))
    assert response.json() == {"user_id": SPECIAL_PK, **ITEM_BODY}


async def test_sort_key_is_sent_and_not_hashed(tmp_path):
    c = Cluster(tmp_path)
    await c.api.post("/tables", json=EVENTS)
    for sk in SORT_KEYS:
        assert (await c.api.put(EVENTS_URL, params={"sk": sk}, json={})).status_code == 201
    counts = [await c.shard_items(sid) for sid in SHARD_URLS]
    assert sorted(counts) == [0, len(SORT_KEYS)]  # both sort keys land on the pk's owner
    assert (await c.api.get(EVENTS_URL, params={"sk": SORT_KEYS[1]})).json()["ts"] == SORT_KEYS[1]
    await c.aclose()


async def test_placement_survives_coordinator_restart(tmp_path):
    first = Cluster(tmp_path, order=("shard-1", "shard-2"))
    second = Cluster(tmp_path, order=("shard-2", "shard-1"))
    for i in range(KEY_COUNT):
        key = f"{TABLE}{RING_KEY_SEPARATOR}u{i}"
        assert first.registry.owner_for_key(key) == second.registry.owner_for_key(key)
    await first.aclose()
    await second.aclose()


def test_sharded_mode_without_injected_backend_routes_through_ring(tmp_path):
    settings = Settings(role="coordinator", catalog_path=tmp_path / CATALOG_FILE)
    with TestClient(create_coordinator_app(settings)) as client:  # runs the lifespan
        assert client.post("/tables", json=USERS).status_code == 201
        response = client.get(item_url("u1"))
    assert response.status_code == NO_SHARDS_STATUS
    assert response.json() == NO_SHARDS
