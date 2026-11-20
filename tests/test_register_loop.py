import asyncio
from dataclasses import replace

import httpx
import pytest
import respx

from kv.coordinator.app import create_coordinator_app
from kv.settings import Settings
from kv.shard.register import registration_loop

COORDINATOR = "http://coordinator:8000"
SHARDS_URL = f"{COORDINATOR}/shards"
SHARD_ID = "s1"
ADVERTISE = "http://s1:8000"
TINY_HEARTBEAT_S = 0.01
WAIT_TIMEOUT_S = 2.0
EXPECTED_BODY = {"id": SHARD_ID, "url": ADVERTISE}

SETTINGS = Settings(
    role="shard",
    shard_id=SHARD_ID,
    advertise_url=ADVERTISE,
    coordinator_url=COORDINATOR,
    heartbeat_s=TINY_HEARTBEAT_S,
)


async def run_until(client, predicate, settings=SETTINGS):
    task = asyncio.create_task(registration_loop(client, settings))
    try:
        async with asyncio.timeout(WAIT_TIMEOUT_S):
            while not predicate():
                await asyncio.sleep(TINY_HEARTBEAT_S)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_loop_retries_after_connection_error():
    outcomes = []

    def first_call_fails(request):
        if not outcomes:
            outcomes.append("error")
            raise httpx.ConnectError("down")
        outcomes.append("created")
        return httpx.Response(201, json=EXPECTED_BODY)

    with respx.mock:
        respx.post(SHARDS_URL).mock(side_effect=first_call_fails)
        async with httpx.AsyncClient() as client:
            await run_until(client, lambda: "created" in outcomes)
    assert outcomes[:2] == ["error", "created"]


async def test_loop_tolerates_trailing_slash_in_coordinator_url():
    settings = replace(SETTINGS, coordinator_url=COORDINATOR + "/")
    with respx.mock:
        route = respx.post(SHARDS_URL).mock(return_value=httpx.Response(201, json=EXPECTED_BODY))
        async with httpx.AsyncClient() as client:
            await run_until(client, lambda: route.called, settings)


async def test_loop_survives_non_2xx():
    with respx.mock:
        route = respx.post(SHARDS_URL).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            await run_until(client, lambda: route.call_count >= 2)


async def test_loop_reregisters_after_coordinator_restart(tmp_path):
    settings = Settings(role="coordinator", mode="single", catalog_path=tmp_path / "c.json")
    app = create_coordinator_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=COORDINATOR) as client:

        async def listed():
            return (await client.get("/shards")).json()

        task = asyncio.create_task(registration_loop(client, SETTINGS))
        try:
            async with asyncio.timeout(WAIT_TIMEOUT_S):
                while await listed() != [EXPECTED_BODY]:
                    await asyncio.sleep(TINY_HEARTBEAT_S)
                await client.delete(f"/shards/{SHARD_ID}")
                while await listed() != [EXPECTED_BODY]:
                    await asyncio.sleep(TINY_HEARTBEAT_S)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
