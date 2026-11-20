import os
from collections.abc import Mapping
from functools import cache

from fastapi import FastAPI

from kv.coordinator.app import create_coordinator_app
from kv.settings import load_settings
from kv.shard.app import create_shard_app


def build_app(env: Mapping[str, str] = os.environ) -> FastAPI:
    settings = load_settings(env)
    return (
        create_coordinator_app(settings)
        if settings.role == "coordinator"
        else create_shard_app(settings)
    )


@cache
def _cached_app() -> FastAPI:
    return build_app()


def __getattr__(name: str) -> FastAPI:
    # Built on first access so importing kv.main needs no KV_* environment.
    if name == "app":
        return _cached_app()
    raise AttributeError(name)
