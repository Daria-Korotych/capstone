from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from kv.settings import Settings
from kv.storage import InMemoryStore

ITEM_PATH = "/internal/items/{table}/{pk:path}"


def create_shard_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    store = InMemoryStore()

    def not_found() -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404)

    # An empty ?sk= is the same as no sk.
    @app.put(ITEM_PATH)
    def put_item(table: str, pk: str, item: dict, response: Response, sk: str | None = None):
        is_new = store.put(table, pk, sk or None, item)
        response.status_code = 201 if is_new else 200
        return item

    @app.get(ITEM_PATH)
    def get_item(table: str, pk: str, sk: str | None = None):
        item = store.get(table, pk, sk or None)
        return item if item is not None else not_found()

    @app.head(ITEM_PATH)
    def head_item(table: str, pk: str, sk: str | None = None):
        return Response(status_code=200 if store.exists(table, pk, sk or None) else 404)

    @app.delete(ITEM_PATH, status_code=204)
    def delete_item(table: str, pk: str, sk: str | None = None):
        store.delete(table, pk, sk or None)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "role": "shard",
            "id": settings.shard_id,
            "items": len(store),
        }

    return app
