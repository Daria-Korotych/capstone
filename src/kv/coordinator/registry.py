from threading import Lock
from typing import Literal

from kv.ring import HashRing


class ShardRegistry:
    """Shard id -> url, plus the ring over ids. Placement depends only on the id."""

    def __init__(self, ring: HashRing) -> None:
        self._ring = ring
        self._urls: dict[str, str] = {}
        self._lock = Lock()  # sync handlers run in a threadpool

    def register(self, shard_id: str, url: str) -> Literal["created", "updated", "unchanged"]:
        with self._lock:
            known = self._urls.get(shard_id)
            if known == url:
                return "unchanged"
            self._urls[shard_id] = url
            self._ring.add(shard_id)
            return "created" if known is None else "updated"

    def remove(self, shard_id: str) -> None:
        with self._lock:
            self._urls.pop(shard_id, None)
            self._ring.remove(shard_id)

    def owner_for_key(self, key: str) -> tuple[str, str]:
        """(shard_id, url) owning key; raises EmptyRingError when no shard is registered."""
        with self._lock:
            shard_id = self._ring.node_for(key)
            return shard_id, self._urls[shard_id]

    def list(self) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(self._urls.items())
