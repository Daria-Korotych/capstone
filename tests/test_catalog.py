import json
import threading
import time

import pytest

from kv.coordinator.catalog import Catalog, TableConflict
from kv.coordinator.models import TableDef

USERS = TableDef(name="users", partition_key="user_id", sort_key=None)
USERS_WITH_SK = TableDef(name="users", partition_key="user_id", sort_key="ts")


def test_create_get_list_and_conflict(tmp_path):
    catalog = Catalog(tmp_path / "catalog.json")
    assert catalog.get(USERS.name) is None
    assert catalog.create(USERS) == "created"
    assert catalog.create(USERS) == "exists"
    assert catalog.get(USERS.name) == USERS
    assert catalog.list() == [USERS]
    with pytest.raises(TableConflict):
        catalog.create(USERS_WITH_SK)


def test_catalog_survives_restart_and_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "catalog.json"
    Catalog(path).create(USERS_WITH_SK)
    assert Catalog(path).get(USERS.name) == USERS_WITH_SK
    assert json.loads(path.read_text())  # valid JSON on disk
    assert [p.name for p in path.parent.iterdir()] == [path.name]  # no temp file left


RACING_THREADS = 16
RACE_WINDOW_S = 0.05


class SlowGetDict(dict):
    """Widens the check-then-write window so an unlocked create reliably races."""

    def get(self, key, default=None):
        value = super().get(key, default)
        time.sleep(RACE_WINDOW_S)
        return value


def test_concurrent_creates_of_one_name_yield_single_winner(tmp_path):
    catalog = Catalog(tmp_path / "catalog.json")
    catalog._tables = SlowGetDict()
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def racer(i: int) -> None:
        try:
            outcomes.append(catalog.create(TableDef(name="t", partition_key=f"pk{i}")))
        except TableConflict:
            pass
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(RACING_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert outcomes == ["created"]
