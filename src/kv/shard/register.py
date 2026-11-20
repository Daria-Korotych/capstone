import asyncio
import logging

import httpx

from kv.settings import Settings

log = logging.getLogger(__name__)


async def registration_loop(client: httpx.AsyncClient, settings: Settings) -> None:
    """POST /shards now and every heartbeat_s; failures are logged, never fatal."""
    body = {"id": settings.shard_id, "url": settings.advertise_url}
    target = f"{settings.coordinator_url.rstrip('/')}/shards"
    while True:
        try:
            (await client.post(target, json=body)).raise_for_status()
        except Exception as exc:
            log.warning("shard registration failed: %r", exc)
        await asyncio.sleep(settings.heartbeat_s)
