from typing import Protocol

from kv.storage import InMemoryStore


class Backend(Protocol):
    async def put(self, table: str, pk: str, sk: str | None, item: dict) -> bool: ...
    async def get(self, table: str, pk: str, sk: str | None) -> dict | None: ...
    async def exists(self, table: str, pk: str, sk: str | None) -> bool: ...
    async def delete(self, table: str, pk: str, sk: str | None) -> None: ...


class LocalBackend:
    def __init__(self, store: InMemoryStore | None = None) -> None:
        self._store = store or InMemoryStore()

    async def put(self, table: str, pk: str, sk: str | None, item: dict) -> bool:
        return self._store.put(table, pk, sk, item)

    async def get(self, table: str, pk: str, sk: str | None) -> dict | None:
        return self._store.get(table, pk, sk)

    async def exists(self, table: str, pk: str, sk: str | None) -> bool:
        return self._store.exists(table, pk, sk)

    async def delete(self, table: str, pk: str, sk: str | None) -> None:
        self._store.delete(table, pk, sk)
