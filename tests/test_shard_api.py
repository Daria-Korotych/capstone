from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from kv.settings import Settings
from kv.shard.app import create_shard_app

SHARD_ID = "s1"
TABLE = "users"
PK = "u1"
ITEM = {"id": "u1", "name": "Ann"}
SPECIAL_PK = "a/b?c#d %25 ключ"
NOT_FOUND = {"error": "not_found"}


@pytest.fixture
def client():
    return TestClient(create_shard_app(Settings(role="shard", shard_id=SHARD_ID)))


def url(pk=PK, table=TABLE):
    return f"/internal/items/{table}/{quote(pk, safe='')}"


def test_put_get_roundtrip(client):
    assert client.put(url(), json=ITEM).status_code == 201
    assert client.put(url(), json=ITEM).status_code == 200
    response = client.get(url())
    assert response.status_code == 200
    assert response.json() == ITEM


def test_get_absent_is_404(client):
    response = client.get(url())
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_head_404_when_absent(client):
    response = client.head(url())
    assert response.status_code == 404
    assert response.content == b""


def test_head_200_when_present(client):
    client.put(url(), json=ITEM)
    response = client.head(url())
    assert response.status_code == 200
    assert response.content == b""


def test_delete_twice_204(client):
    client.put(url(), json=ITEM)
    assert client.delete(url()).status_code == 204
    assert client.delete(url()).status_code == 204
    assert client.get(url()).status_code == 404


def test_sk_is_part_of_the_key(client):
    client.put(url(), params={"sk": "a"}, json={"v": "a"})
    assert client.get(url()).status_code == 404
    assert client.get(url(), params={"sk": "a"}).json() == {"v": "a"}


def test_empty_sk_is_treated_as_absent(client):
    client.put(url(), json=ITEM)
    assert client.get(url(), params={"sk": ""}).json() == ITEM


def test_pk_with_slash_and_unicode_roundtrip(client):
    client.put(url(SPECIAL_PK), json=ITEM)
    assert client.get(url(SPECIAL_PK)).json() == ITEM


def test_health_reports_item_count(client):
    client.put(url(), json=ITEM)
    assert client.get("/health").json() == {
        "status": "ok",
        "role": "shard",
        "id": SHARD_ID,
        "items": 1,
    }
