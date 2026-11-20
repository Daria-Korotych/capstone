import re
from pathlib import Path

import yaml

from kv.coordinator.app import create_coordinator_app
from kv.settings import Settings

CONTRACT = Path(__file__).parent.parent / "api" / "openapi.yaml"
HTTP_METHODS = {"get", "put", "post", "delete", "head"}
PATH_CONVERTER = re.compile(r"\{(\w+):path\}")


def operations(paths: dict) -> set[tuple[str, str]]:
    return {
        (PATH_CONVERTER.sub(r"{\1}", path), method.upper())
        for path, item in paths.items()
        for method in item
        if method in HTTP_METHODS
    }


def test_openapi_matches_contract(tmp_path):
    settings = Settings(role="coordinator", mode="single", catalog_path=tmp_path / "c.json")
    app = create_coordinator_app(settings)
    implemented = {
        (PATH_CONVERTER.sub(r"{\1}", r.path), m)
        for r in app.routes
        for m in getattr(r, "methods", ())
        if m not in {"OPTIONS"}
        and r.path not in {"/openapi.json", "/docs", "/redoc"}
        and not r.path.startswith("/docs/")
    }
    contract = operations(yaml.safe_load(CONTRACT.read_text())["paths"])
    assert implemented == contract
