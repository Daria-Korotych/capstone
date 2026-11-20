import itertools
import subprocess
import sys

import pytest

from kv.ring import EmptyRingError, HashRing, stable_hash
from kv.settings import DEFAULT_VNODES

SHARD_1, SHARD_2, SHARD_3 = "shard-1", "shard-2", "shard-3"
SAMPLE_KEY_COUNT = 10_000
SAMPLE_KEYS = [f"usertable\x1fuser{i}" for i in range(SAMPLE_KEY_COUNT)]
SMALL_VNODES = 8
PROCESS_KEY_COUNT = 100
HASH_SEEDS = ("1", "2")
# Ideal share moved when a 3rd node joins is 1/3.
MOVED_MIN, MOVED_MAX = 0.25, 0.42
SHARE_MIN, SHARE_MAX = 0.40, 0.60


def ring_of(*node_ids, vnodes=DEFAULT_VNODES):
    ring = HashRing(vnodes)
    for node_id in node_ids:
        ring.add(node_id)
    return ring


def placement(ring):
    return {k: ring.node_for(k) for k in SAMPLE_KEYS}


def test_empty_ring_raises():
    with pytest.raises(EmptyRingError):
        HashRing(vnodes=SMALL_VNODES).node_for("k")


def test_add_is_idempotent():
    ring = ring_of(SHARD_1)
    ring.add(SHARD_1)
    assert ring.nodes == frozenset({SHARD_1})
    assert placement(ring) == placement(ring_of(SHARD_1))


def test_remove_is_idempotent():
    ring = ring_of(SHARD_1, SHARD_2)
    ring.remove(SHARD_2)
    ring.remove(SHARD_2)
    assert ring.nodes == frozenset({SHARD_1})


def test_same_key_same_node():
    ring = ring_of(SHARD_1, SHARD_2)
    assert ring.node_for("x") == ring.node_for("x")


def test_placement_stable_across_processes():
    script = (
        "from kv.ring import HashRing\n"
        f"r = HashRing({SMALL_VNODES})\n"
        f"r.add({SHARD_1!r}); r.add({SHARD_2!r})\n"
        f"print([r.node_for(f'k{{i}}') for i in range({PROCESS_KEY_COUNT})])\n"
    )
    outputs = [
        subprocess.run(
            [sys.executable, "-c", script],
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in HASH_SEEDS
    ]
    assert outputs[0] == outputs[1]


def test_adding_node_moves_keys_only_to_new_node():
    before = placement(ring_of(SHARD_1, SHARD_2))
    after = placement(ring_of(SHARD_1, SHARD_2, SHARD_3))
    moved = [k for k in SAMPLE_KEYS if before[k] != after[k]]
    assert all(after[k] == SHARD_3 for k in moved)
    assert MOVED_MIN < len(moved) / SAMPLE_KEY_COUNT < MOVED_MAX


def test_remove_returns_keys_to_previous_owner():
    ring = ring_of(SHARD_1, SHARD_2, SHARD_3)
    ring.remove(SHARD_3)
    assert placement(ring) == placement(ring_of(SHARD_1, SHARD_2))


def test_wraparound():
    ring = ring_of(SHARD_1, SHARD_2, vnodes=1)
    points = sorted((stable_hash(f"{n}#0"), n) for n in (SHARD_1, SHARD_2))
    max_point, smallest_owner = points[-1][0], points[0][1]
    key = next(k for k in (f"k{i}" for i in itertools.count()) if stable_hash(k) > max_point)
    assert ring.node_for(key) == smallest_owner


def test_distribution_at_chosen_vnodes():
    ring = ring_of(SHARD_1, SHARD_2)
    owned = sum(1 for k in SAMPLE_KEYS if ring.node_for(k) == SHARD_1)
    assert SHARE_MIN < owned / SAMPLE_KEY_COUNT < SHARE_MAX
