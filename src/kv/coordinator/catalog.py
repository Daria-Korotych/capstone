import json
import os
import threading
from pathlib import Path
from typing import Literal

from kv.coordinator.models import TableDef


class TableConflict(Exception):
    """A table with this name exists with different keys."""


class Catalog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._tables: dict[str, TableDef] = {}
        self._lock = threading.Lock()
        if path.exists():
            self._tables = {t["name"]: TableDef(**t) for t in json.loads(path.read_text())}

    def create(self, t: TableDef) -> Literal["created", "exists"]:
        with self._lock:
            current = self._tables.get(t.name)
            if current is not None:
                if current == t:
                    return "exists"
                raise TableConflict(t.name)
            self._tables[t.name] = t
            self._save()
            return "created"

    def get(self, name: str) -> TableDef | None:
        return self._tables.get(name)

    def list(self) -> list[TableDef]:
        with self._lock:
            return list(self._tables.values())

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps([t.model_dump() for t in self._tables.values()]))
        os.replace(tmp, self._path)
