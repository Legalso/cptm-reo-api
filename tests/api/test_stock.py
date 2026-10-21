"""Rotas de estoque e inspeções: sucesso, 422, 401, 403 e idempotência HTTP."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.enums import Role, SleeperStatus
from tests.conftest import Catalog, SleeperFactory, UserFactory, auth_headers


def inspection_body(tag: str, result: str = "rejected", **extra: Any) -> dict[str, Any]:
    return {
        "rfid_tag": tag,
        "conservation": "poor",
        "has_cracks": True,
        "biological_attack": True,
        "moisture": "wet",
        "result": result,
        "duration_seconds": 120,
        **extra,
    }


async def test_movement_flow_and_listing(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user(Role.OPERATOR))
    sleeper = await make_sleeper()
    body = {
        "rfid_tag": sleeper.rfid_tag,
        "kind": "withdrawal",
        "requisition_number": "RM-2026-0042",
        "client_uuid": str(uuid.uuid4()),
    }

    first = await client.post("/estoque/movimentacao", json=body, headers=headers)
    again = await client.post("/estoque/movimentacao", json=body, headers=headers)

    assert first.status_code == 201
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    detail = await client.get(f"/dormentes/{sleeper.id}", headers=headers)
    assert detail.json()["status"] == "withdrawn"

    listing = await client.get(
        "/estoque/movimentacoes", params={"kind": "withdrawal"}, headers=headers
    )
    assert listing.status_code == 200 and listing.json()["total"] == 1


async def test_movement_rule_violation_is_409(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user())
    sleeper = await make_sleeper(status=SleeperStatus.DISCARDED)
    resp = await client.post(
        "/estoque/movimentacao",
        json={
            "sleeper_id": str(sleeper.id),
            "kind": "transfer",
            "to_location_id": str(catalog.street.id),
        },
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "sleeper_discarded"


@pytest.mark.parametrize(
    "body",
    [
        {"rfid_tag": "X", "kind": "withdrawal"},  # sem RM
        {"rfid_tag": "X", "kind": "entry"},  # sem destino
        {"kind": "withdrawal", "requisition_number": "RM"},  # sem dormente
        {"rfid_tag": "X", "sleeper_id": str(uuid.uuid4()), "kind": "transfer"},
        {"rfid_tag": "X", "kind": "teleporte"},
    ],
)
async def test_movement_validation(
    client: AsyncClient, make_user: UserFactory, body: dict[str, Any]
) -> None:
    resp = await client.post(
        "/estoque/movimentacao", json=body, headers=auth_headers(await make_user())
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/estoque/movimentacao",
        "/estoque/localizacao",
        "/estoque/inventario",
        "/estoque/ocorrencias",
    ],
)
async def test_stock_writes_require_auth_and_field_role(
    client: AsyncClient, make_user: UserFactory, path: str
) -> None:
    assert (await client.post(path, json={})).status_code == 401
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    assert (await client.post(path, json={}, headers=supervisor)).status_code == 403


@pytest.mark.parametrize(
    "path", ["/estoque/movimentacoes", "/estoque/inventarios", "/estoque/ocorrencias", "/inspecoes"]
)
async def test_listings_auth_and_period_validation(
    client: AsyncClient, make_user: UserFactory, path: str
) -> None:
    assert (await client.get(path)).status_code == 401
    headers = auth_headers(await make_user(Role.SUPERVISOR))
    assert (await client.get(path, headers=headers)).status_code == 200
    bad = await client.get(
        path, params={"de": "2026-10-21T00:00:00Z", "ate": "2026-10-01T00:00:00Z"}, headers=headers
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_period"


async def test_location_shortcut(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user())
    sleeper = await make_sleeper()
    resp = await client.post(
        "/estoque/localizacao",
        json={"rfid_tag": sleeper.rfid_tag, "location_id": str(catalog.other_street.id)},
        headers=headers,
    )
    assert resp.status_code == 201 and resp.json()["kind"] == "transfer"
    missing = await client.post(
        "/estoque/localizacao", json={"rfid_tag": sleeper.rfid_tag}, headers=headers
    )
    assert missing.status_code == 422


async def test_inventory_count(
    client: AsyncClient, make_user: UserFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user())
    body = {
        "location_id": str(catalog.street.id),
        "species_id": str(catalog.species.id),
        "quantity": 42,
        "read_tags": ["a1", "A1", "b2"],
    }
    resp = await client.post("/estoque/inventario", json=body, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["read_tags"] == ["A1", "B2"]
    negative = await client.post(
        "/estoque/inventario", json={**body, "quantity": -1}, headers=headers
    )
    assert negative.status_code == 422
    unknown = await client.post(
        "/estoque/inventario", json={**body, "species_id": str(uuid.uuid4())}, headers=headers
    )
    assert unknown.status_code == 404
    listing = await client.get(
        "/estoque/inventarios", params={"location_id": str(catalog.street.id)}, headers=headers
    )
    assert listing.json()["total"] == 1


async def test_occurrence(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user())
    sleeper = await make_sleeper()
    resp = await client.post(
        "/estoque/ocorrencias",
        json={"rfid_tag": sleeper.rfid_tag, "kind": "damage", "description": "Rachado"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["location_id"] == str(catalog.street.id)
    invalid = await client.post(
        "/estoque/ocorrencias", json={"kind": "damage", "description": "Sem lugar"}, headers=headers
    )
    assert invalid.status_code == 422
    listing = await client.get("/estoque/ocorrencias", params={"kind": "damage"}, headers=headers)
    assert listing.json()["total"] == 1


async def test_inspection_flow(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    sleeper = await make_sleeper()
    body = inspection_body(sleeper.rfid_tag, client_uuid=str(uuid.uuid4()))

    created = await client.post("/inspecoes", json=body, headers=tech)
    again = await client.post("/inspecoes", json=body, headers=tech)

    assert created.status_code == 201 and again.status_code == 200
    detail = await client.get(f"/inspecoes/{created.json()['id']}", headers=tech)
    assert detail.status_code == 200 and detail.json()["result"] == "rejected"
    sleeper_now = await client.get(f"/dormentes/{sleeper.id}", headers=tech)
    assert sleeper_now.json()["status"] == "quarantine"
    history = await client.get(f"/dormentes/{sleeper.id}/historico", headers=tech)
    assert [i["type"] for i in history.json()["items"]] == ["inspection"]


async def test_inspection_auth_roles_and_validation(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    sleeper = await make_sleeper()
    body = inspection_body(sleeper.rfid_tag)
    assert (await client.post("/inspecoes", json=body)).status_code == 401
    operator = auth_headers(await make_user(Role.OPERATOR))
    assert (await client.post("/inspecoes", json=body, headers=operator)).status_code == 403
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    bad = await client.post("/inspecoes", json={**body, "conservation": "otimo"}, headers=tech)
    assert bad.status_code == 422
    contradictory = await client.post(
        "/inspecoes",
        json={**body, "species_confirmed": True, "species_corrected_id": str(uuid.uuid4())},
        headers=tech,
    )
    assert contradictory.status_code == 422
    missing = await client.get(f"/inspecoes/{uuid.uuid4()}", headers=tech)
    assert missing.status_code == 404
