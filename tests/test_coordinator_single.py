import pytest
from fastapi.testclient import TestClient

from kv.coordinator.app import create_coordinator_app
from kv.settings import Settings

SINGLE_MODE = "single"
USERS = {"name": "users", "partition_key": "user_id"}
EVENTS = {"name": "events", "partition_key": "user_id", "sort_key": "ts"}
USERS_URL = "/tables/users/items/u1"
EVENTS_URL = "/tables/events/items/u1"
ITEM_BODY = {"name": "A"}
STORED_ITEM = {"user_id": "u1", "name": "A"}
BAD_TABLE_NAME = {"name": "bad name!", "partition_key": "id"}
SAME_KEYS_TABLE = {"name": "dup", "partition_key": "id", "sort_key": "id"}
CATALOG_FILE = "c.json"
OTHER_PK = "u2"
NON_STRING_PK = 1
SK_FOR_SIMPLE = "x"
SK_1, SK_2 = "t1", "t2"
UNKNOWN_TABLE = "nope"
UNKNOWN_URL = f"/tables/{UNKNOWN_TABLE}/items/u1"
EMPTY_PK_URL = "/tables/users/items/"
OTHER_PARTITION_KEY = "other"


def make_client(tmp_path) -> TestClient:
    settings = Settings(role="coordinator", mode=SINGLE_MODE, catalog_path=tmp_path / CATALOG_FILE)
    return TestClient(create_coordinator_app(settings))


@pytest.fixture
def client(tmp_path):
    c = make_client(tmp_path)
    assert c.post("/tables", json=USERS).status_code == 201
    assert c.post("/tables", json=EVENTS).status_code == 201
    return c


def test_create_table_201_then_identical_200_then_different_409(client):
    assert client.post("/tables", json=USERS).status_code == 200
    conflict = client.post("/tables", json={**USERS, "partition_key": OTHER_PARTITION_KEY})
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "conflict"


def test_list_and_get_table(client):
    assert client.get("/tables/users").json() == USERS
    assert {t["name"] for t in client.get("/tables").json()} == {"users", "events"}
    assert client.get(f"/tables/{UNKNOWN_TABLE}").status_code == 404


def test_sort_key_omitted_for_simple_table_present_for_composite(tmp_path):
    c = make_client(tmp_path)
    assert "sort_key" not in c.post("/tables", json=USERS).json()
    assert c.post("/tables", json=EVENTS).json()["sort_key"] == "ts"
    assert "sort_key" not in c.get("/tables/users").json()
    assert c.get("/tables/events").json()["sort_key"] == "ts"
    listed = {t["name"]: t for t in c.get("/tables").json()}
    assert "sort_key" not in listed["users"]
    assert listed["events"]["sort_key"] == "ts"


def test_invalid_table_name_400(client):
    response = client.post("/tables", json=BAD_TABLE_NAME)
    assert response.status_code == 400
    assert response.json()["error"] == "bad_request"


def test_put_by_key(client):
    assert client.put(USERS_URL, json=ITEM_BODY).status_code == 201
    assert client.put(USERS_URL, json=ITEM_BODY).status_code == 200
    assert client.get(USERS_URL).json() == STORED_ITEM


def test_composite_key_item_roundtrip(client):
    url = f"{EVENTS_URL}?sk={SK_1}"
    assert client.put(url, json=ITEM_BODY).status_code == 201
    assert client.get(url).json() == {"user_id": "u1", "ts": SK_1, "name": "A"}
    assert client.get(f"{EVENTS_URL}?sk={SK_2}").status_code == 404


def test_put_body_key_differs_from_path_400(client):
    assert client.put(USERS_URL, json={"user_id": OTHER_PK}).status_code == 400
    assert client.put(USERS_URL, json={"user_id": NON_STRING_PK}).status_code == 400
    assert client.put(USERS_URL, json=[1]).status_code == 400
    assert client.put(USERS_URL, json={"user_id": "u1"}).status_code == 201


def test_sk_required_for_composite_table_400(client):
    assert client.put(EVENTS_URL, json=ITEM_BODY).status_code == 400
    assert client.get(EVENTS_URL).status_code == 400


def test_sk_rejected_for_simple_table_400(client):
    assert client.put(f"{USERS_URL}?sk={SK_FOR_SIMPLE}", json=ITEM_BODY).status_code == 400
    assert client.head(f"{USERS_URL}?sk={SK_FOR_SIMPLE}").status_code == 400


def test_head_exists_200_and_404(client):
    assert client.head(USERS_URL).status_code == 404
    client.put(USERS_URL, json=ITEM_BODY)
    assert client.head(USERS_URL).status_code == 200


def test_delete_idempotent_204(client):
    client.put(USERS_URL, json=ITEM_BODY)
    assert client.delete(USERS_URL).status_code == 204
    assert client.delete(USERS_URL).status_code == 204
    assert client.get(USERS_URL).status_code == 404


def test_unknown_table_404(client):
    url = UNKNOWN_URL
    assert client.put(url, json=ITEM_BODY).status_code == 404
    assert client.get(url).status_code == 404
    assert client.head(url).status_code == 404
    assert client.delete(url).status_code == 404
    # unknown table outranks a malformed body
    assert client.put(url, json=[1]).status_code == 404


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "mode": SINGLE_MODE, "shards": 0}


def test_sharded_mode_requires_injected_backend(tmp_path):
    settings = Settings(role="coordinator", mode="sharded", catalog_path=tmp_path / CATALOG_FILE)
    with pytest.raises(ValueError):
        create_coordinator_app(settings)


def test_empty_pk_400(client):
    assert client.put(EMPTY_PK_URL, json=ITEM_BODY).status_code == 400
    assert client.get(EMPTY_PK_URL).status_code == 400
    assert client.head(EMPTY_PK_URL).status_code == 400
    assert client.delete(EMPTY_PK_URL).status_code == 400


def test_same_partition_and_sort_key_400(client):
    assert client.post("/tables", json=SAME_KEYS_TABLE).status_code == 400
