import hashlib
from bisect import bisect_right, insort

from kv.settings import DEFAULT_VNODES

# ADR-0006: single source of truth lives in settings.
VNODES_DEFAULT = DEFAULT_VNODES
HASH_BYTES = 8


class EmptyRingError(Exception):
    """node_for was called on a ring with no nodes."""


def stable_hash(data: str) -> int:
    """64-bit hash, identical across processes (unlike builtin hash())."""
    digest = hashlib.blake2b(data.encode(), digest_size=HASH_BYTES).digest()
    return int.from_bytes(digest, "big")


class HashRing:
    """Consistent hashing ring per ADR-0006. Not thread-safe; callers synchronise."""

    def __init__(self, vnodes: int = VNODES_DEFAULT) -> None:
        self._vnodes = vnodes
        self._points: list[tuple[int, str]] = []
        self._nodes: set[str] = set()

    @property
    def nodes(self) -> frozenset[str]:
        return frozenset(self._nodes)

    def add(self, node_id: str) -> None:
        if node_id in self._nodes:
            return
        self._nodes.add(node_id)
        for i in range(self._vnodes):
            insort(self._points, (stable_hash(f"{node_id}#{i}"), node_id))

    def remove(self, node_id: str) -> None:
        if node_id not in self._nodes:
            return
        self._nodes.remove(node_id)
        self._points = [p for p in self._points if p[1] != node_id]

    def node_for(self, key: str) -> str:
        if not self._points:
            raise EmptyRingError
        # Max-char sentinel: a key hashing exactly onto a point goes to the next point.
        index = bisect_right(self._points, (stable_hash(key), chr(0x10FFFF)))
        return self._points[index % len(self._points)][1]
