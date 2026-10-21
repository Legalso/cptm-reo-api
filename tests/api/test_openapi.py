"""Contrato com o front e qualidade do /docs."""

import pytest
from httpx import AsyncClient

# Const ENDPOINTS de mpliHD.github.io/src/App.jsx — estes paths não podem mudar.
SITE_ENDPOINTS = [
    ("post", "/auth/login"),
    ("post", "/auth/mfa"),
    ("post", "/auth/mfa-offline"),
    ("get", "/usuarios"),
    ("post", "/usuarios"),
    ("patch", "/usuarios/{user_id}/papel"),
    ("post", "/usuarios/convite"),
    ("post", "/estoque/movimentacao"),
    ("post", "/estoque/inventario"),
    ("post", "/estoque/localizacao"),
    ("post", "/estoque/ocorrencias"),
    ("post", "/sincronizacao/replicar"),
    ("get", "/sincronizacao/status"),
    ("get", "/monitoramento/status"),
    ("get", "/logs"),
]


@pytest.fixture
async def spec(client: AsyncClient) -> dict:  # type: ignore[type-arg]
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()  # type: ignore[no-any-return]


async def test_site_endpoints_exist(spec: dict) -> None:  # type: ignore[type-arg]
    for method, path in SITE_ENDPOINTS:
        assert method in spec["paths"].get(path, {}), f"{method.upper()} {path} sumiu"


async def test_every_route_has_summary_and_tag(spec: dict) -> None:  # type: ignore[type-arg]
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            assert op.get("summary"), f"{method} {path} sem summary"
            assert op.get("tags"), f"{method} {path} sem tag"


async def test_validation_errors_documented_in_standard_format(spec: dict) -> None:  # type: ignore[type-arg]
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    login_422 = spec["paths"]["/auth/login"]["post"]["responses"]["422"]
    ref = login_422["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ValidationErrorResponse")
