import threading

Key = tuple[str, str, str | None]


class InMemoryStore:
    def __init__(self) -> None:
        self._items: dict[Key, dict] = {}
        self._lock = threading.Lock()

    def put(self, table: str, pk: str, sk: str | None, item: dict) -> bool:
        """Store item; True if the key was new."""
        with self._lock:
            is_new = (table, pk, sk) not in self._items
            self._items[(table, pk, sk)] = item
            return is_new

    def get(self, table: str, pk: str, sk: str | None) -> dict | None:
        with self._lock:
            item = self._items.get((table, pk, sk))
            return None if item is None else dict(item)

    def exists(self, table: str, pk: str, sk: str | None) -> bool:
        with self._lock:
            return (table, pk, sk) in self._items

    def delete(self, table: str, pk: str, sk: str | None) -> None:
        with self._lock:
            self._items.pop((table, pk, sk), None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
