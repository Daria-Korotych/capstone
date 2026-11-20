from urllib.parse import quote

import httpx

from kv.coordinator.errors import ApiError
from kv.coordinator.registry import ShardRegistry
from kv.ring import EmptyRingError

RING_KEY_SEPARATOR = (
    "\x1f"  # ADR-0007: ring key is table + separator + pk; the sort key is not hashed
)
STATUS_NOT_FOUND = 404
STATUS_ERROR_FLOOR = 400  # any other 4xx means the internal contract is broken


class ShardedBackend:
    """Forwards each call to the shard that owns the (table, pk) ring key. No retries."""

    def __init__(self, registry: ShardRegistry, client: httpx.AsyncClient) -> None:
        self._registry = registry
        self._client = client

    async def _call(
        self, method: str, table: str, pk: str, sk: str | None, **kwargs
    ) -> httpx.Response:
        try:
            shard_id, base = self._registry.owner_for_key(f"{table}{RING_KEY_SEPARATOR}{pk}")
        except EmptyRingError:
            raise ApiError(503, "no_shards") from None
        url = f"{base}/internal/items/{table}/{quote(pk, safe='')}"
        try:
            response = await self._client.request(
                method, url, params={} if sk is None else {"sk": sk}, **kwargs
            )
        except httpx.TransportError:  # includes timeouts
            raise ApiError(502, "shard_unavailable", shard=shard_id) from None
        if response.status_code >= STATUS_ERROR_FLOOR and response.status_code != STATUS_NOT_FOUND:
            raise ApiError(502, "shard_unavailable", shard=shard_id)
        return response

    async def put(self, table: str, pk: str, sk: str | None, item: dict) -> bool:
        return (await self._call("PUT", table, pk, sk, json=item)).status_code == 201

    async def get(self, table: str, pk: str, sk: str | None) -> dict | None:
        response = await self._call("GET", table, pk, sk)
        return None if response.status_code == STATUS_NOT_FOUND else response.json()

    async def exists(self, table: str, pk: str, sk: str | None) -> bool:
        return (await self._call("HEAD", table, pk, sk)).status_code != STATUS_NOT_FOUND

    async def delete(self, table: str, pk: str, sk: str | None) -> None:
        await self._call("DELETE", table, pk, sk)
