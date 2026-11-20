from kv.storage import InMemoryStore

TABLE = "t"
PK = "p"
SK = "x"
ITEM = {"v": 1}
MUTATED_VALUE = 2


def test_put_new_returns_true_then_false():
    store = InMemoryStore()
    assert store.put(TABLE, PK, None, ITEM) is True
    assert store.put(TABLE, PK, None, ITEM) is False


def test_get_missing_is_none():
    assert InMemoryStore().get(TABLE, PK, None) is None


def test_delete_missing_is_noop():
    InMemoryStore().delete(TABLE, PK, None)


def test_items_with_and_without_sk_do_not_collide():
    store = InMemoryStore()
    store.put(TABLE, PK, None, {"v": "no-sk"})
    store.put(TABLE, PK, SK, {"v": "sk"})
    assert store.get(TABLE, PK, None) == {"v": "no-sk"}
    assert store.get(TABLE, PK, SK) == {"v": "sk"}
    store.delete(TABLE, PK, None)
    assert not store.exists(TABLE, PK, None)
    assert store.exists(TABLE, PK, SK)


def test_get_returns_copy():
    store = InMemoryStore()
    store.put(TABLE, PK, None, dict(ITEM))
    store.get(TABLE, PK, None)["v"] = MUTATED_VALUE
    assert store.get(TABLE, PK, None) == ITEM
