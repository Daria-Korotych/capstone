from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kv.coordinator.backends import Backend, LocalBackend
from kv.coordinator.catalog import Catalog, TableConflict
from kv.coordinator.errors import ApiError
from kv.coordinator.models import TableDef
from kv.settings import Settings

ITEM_PATH = "/tables/{table}/items/{pk:path}"


def create_coordinator_app(settings: Settings, backend: Backend | None = None) -> FastAPI:
    if backend is None:
        if settings.mode == "sharded":
            raise ValueError("sharded mode requires an injected backend")
        backend = LocalBackend()
    catalog = Catalog(settings.catalog_path)
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(exc.body, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError):
        return JSONResponse({"error": "bad_request", "detail": str(exc.errors())}, status_code=400)

    def bad_request(detail: str) -> ApiError:
        return ApiError(400, "bad_request", detail)

    def table_of(name: str) -> TableDef:
        table = catalog.get(name)
        if table is None:
            raise ApiError(404, "not_found", f"unknown table {name!r}")
        return table

    def sort_key_of(table: TableDef, pk: str, sk: str | None) -> str | None:
        if not pk:
            raise bad_request("pk must not be empty")
        sk = sk or None  # an empty ?sk= is the same as no sk
        if (sk is None) != (table.sort_key is None):
            raise bad_request("sk is required if and only if the table has a sort_key")
        return sk

    @app.post("/tables", response_model=TableDef, response_model_exclude_none=True)
    def create_table(table: TableDef, response: Response):
        try:
            outcome = catalog.create(table)
        except TableConflict:
            raise ApiError(409, "conflict", "table exists with different keys") from None
        response.status_code = 201 if outcome == "created" else 200
        return table

    @app.get("/tables", response_model_exclude_none=True)
    def list_tables() -> list[TableDef]:
        return catalog.list()

    @app.get("/tables/{table}", response_model_exclude_none=True)
    def get_table(table: str) -> TableDef:
        return table_of(table)

    # The body is parsed by hand: the table lookup (404) must come before body validation (400).
    @app.put(ITEM_PATH)
    async def put_item(
        table: str, pk: str, request: Request, response: Response, sk: str | None = None
    ):
        t = table_of(table)
        sk = sort_key_of(t, pk, sk)
        try:
            body = await request.json()
        except ValueError:
            raise bad_request("body must be JSON") from None
        if not isinstance(body, dict):
            raise bad_request("body must be a JSON object")
        keys = {t.partition_key: pk, **({t.sort_key: sk} if t.sort_key else {})}
        for attr, value in keys.items():
            if attr in body and body[attr] != value:
                raise bad_request(f"{attr} in body must be the string {value!r} from the path")
        item = {**body, **keys}
        response.status_code = 201 if await backend.put(table, pk, sk, item) else 200
        return item

    @app.get(ITEM_PATH)
    async def get_item(table: str, pk: str, sk: str | None = None):
        item = await backend.get(table, pk, sort_key_of(table_of(table), pk, sk))
        if item is None:
            raise ApiError(404, "not_found")
        return item

    @app.head(ITEM_PATH)
    async def head_item(table: str, pk: str, sk: str | None = None):
        found = await backend.exists(table, pk, sort_key_of(table_of(table), pk, sk))
        return Response(status_code=200 if found else 404)

    @app.delete(ITEM_PATH, status_code=204)
    async def delete_item(table: str, pk: str, sk: str | None = None):
        await backend.delete(table, pk, sort_key_of(table_of(table), pk, sk))

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": settings.mode, "shards": 0}  # Task 7: registry count

    return app
