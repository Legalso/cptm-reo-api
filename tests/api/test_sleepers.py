"""Dormentes: cadastro, tag, filtros, edição e histórico."""

import uuid
from typing import Any

from httpx import AsyncClient

from app.models.enums import Role, SleeperStatus
from tests.conftest import Catalog, SleeperFactory, UserFactory, auth_headers


def new_sleeper(catalog: Catalog, **overrides: Any) -> dict[str, Any]:
    return {
        "rfid_tag": " e2801160600002084e5a1b21 ",
        "registration_record": "AR00224-02",
        "species_id": str(catalog.species.id),
        "wood_class": "1a",
        "length_m": 2.8,
        "treatment": "CCA",
        "supplier": "Granoski",
        "manufacture_year": 2024,
        "location_id": str(catalog.street.id),
        **overrides,
    }


async def test_operator_registers_sleeper_with_entry(
    client: AsyncClient, make_user: UserFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user(Role.OPERATOR))

    resp = await client.post("/dormentes", json=new_sleeper(catalog), headers=headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["rfid_tag"] == "E2801160600002084E5A1B21"
    assert body["status"] == "in_stock"
    assert body["current_location"]["name"] == "Rua 08"
    assert body["species"]["code"] == "13"

    history = await client.get(f"/dormentes/{body['id']}/historico", headers=headers)
    assert history.status_code == 200
    items = history.json()["items"]
    assert [i["type"] for i in items] == ["movement"]
    assert items[0]["movement"]["kind"] == "entry"


async def test_register_is_idempotent_by_client_uuid(
    client: AsyncClient, admin_headers: dict[str, str], catalog: Catalog
) -> None:
    payload = new_sleeper(catalog, client_uuid=str(uuid.uuid4()))
    first = await client.post("/dormentes", json=payload, headers=admin_headers)
    second = await client.post("/dormentes", json=payload, headers=admin_headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_register_rejects_duplicate_tag_and_bad_data(
    client: AsyncClient, admin_headers: dict[str, str], catalog: Catalog
) -> None:
    await client.post("/dormentes", json=new_sleeper(catalog), headers=admin_headers)
    dup = await client.post("/dormentes", json=new_sleeper(catalog), headers=admin_headers)
    assert dup.status_code == 409
    assert dup.json()["code"] == "rfid_tag_taken"

    no_location = new_sleeper(catalog, rfid_tag="T2")
    no_location.pop("location_id")
    assert (
        await client.post("/dormentes", json=no_location, headers=admin_headers)
    ).status_code == 422
    future = new_sleeper(catalog, rfid_tag="T3", occurred_at="2099-01-01T00:00:00Z")
    resp = await client.post("/dormentes", json=future, headers=admin_headers)
    assert resp.status_code == 422 and resp.json()["code"] == "future_timestamp"


async def test_register_into_inactive_location_fails(
    client: AsyncClient, admin_headers: dict[str, str], catalog: Catalog, session: Any
) -> None:
    catalog.other_street.active = False
    await session.flush()
    resp = await client.post(
        "/dormentes",
        json=new_sleeper(catalog, location_id=str(catalog.other_street.id)),
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "location_inactive"


async def test_sleeper_routes_auth_and_roles(
    client: AsyncClient, make_user: UserFactory, catalog: Catalog
) -> None:
    assert (await client.get("/dormentes")).status_code == 401
    assert (await client.get("/dormentes/tag/X")).status_code == 401
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    assert (await client.get("/dormentes", headers=supervisor)).status_code == 200
    resp = await client.post("/dormentes", json=new_sleeper(catalog), headers=supervisor)
    assert resp.status_code == 403


async def test_get_by_tag_found_and_not_found(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    headers = auth_headers(await make_user())
    sleeper = await make_sleeper(tag="ABC123")

    found = await client.get("/dormentes/tag/abc123", headers=headers)
    assert found.status_code == 200 and found.json()["id"] == str(sleeper.id)

    missing = await client.get("/dormentes/tag/NAOEXISTE", headers=headers)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Tag RFID não cadastrada.", "code": "sleeper_not_found"}


async def test_list_filters(
    client: AsyncClient,
    make_user: UserFactory,
    make_sleeper: SleeperFactory,
    catalog: Catalog,
) -> None:
    headers = auth_headers(await make_user())
    in_street = await make_sleeper(tag="F1")
    other = await make_sleeper(tag="F2", location=catalog.other_street)
    await make_sleeper(tag="F3", status=SleeperStatus.WITHDRAWN)

    by_yard = await client.get(
        "/dormentes", params={"location_id": str(catalog.warehouse.id)}, headers=headers
    )
    assert {s["id"] for s in by_yard.json()["items"]} == {str(in_street.id), str(other.id)}
    by_status = await client.get("/dormentes", params={"status": "withdrawn"}, headers=headers)
    assert by_status.json()["total"] == 1
    by_tag = await client.get("/dormentes", params={"q": "f2"}, headers=headers)
    assert [s["id"] for s in by_tag.json()["items"]] == [str(other.id)]
    bad = await client.get("/dormentes", params={"status": "perdido"}, headers=headers)
    assert bad.status_code == 422


async def test_update_plate_fields_and_audit(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    headers = auth_headers(await make_user(Role.OPERATOR))
    sleeper = await make_sleeper()
    resp = await client.patch(
        f"/dormentes/{sleeper.id}", json={"wood_class": "1b"}, headers=headers
    )
    assert resp.status_code == 200 and resp.json()["wood_class"] == "1b"
    bad = await client.patch(
        f"/dormentes/{sleeper.id}", json={"manufacture_year": 1500}, headers=headers
    )
    assert bad.status_code == 422


async def test_species_change_requires_specialist(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    sleeper = await make_sleeper()
    operator = auth_headers(await make_user(Role.OPERATOR))
    specialist = auth_headers(await make_user(Role.SPECIALIST))

    denied = await client.patch(
        f"/dormentes/{sleeper.id}", json={"species_id": None}, headers=operator
    )
    assert denied.status_code == 403
    ok = await client.patch(
        f"/dormentes/{sleeper.id}", json={"species_id": None}, headers=specialist
    )
    assert ok.status_code == 200 and ok.json()["species"] is None


async def test_manual_status_rules(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    operator = auth_headers(await make_user(Role.OPERATOR))
    sleeper = await make_sleeper()

    denied = await client.patch(
        f"/dormentes/{sleeper.id}", json={"status": "quarantine"}, headers=operator
    )
    assert denied.status_code == 403
    invalid = await client.patch(
        f"/dormentes/{sleeper.id}", json={"status": "withdrawn"}, headers=tech
    )
    assert invalid.status_code == 409 and invalid.json()["code"] == "invalid_status_transition"

    discarded = await client.patch(
        f"/dormentes/{sleeper.id}", json={"status": "discarded"}, headers=tech
    )
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"
    back = await client.patch(f"/dormentes/{sleeper.id}", json={"status": "in_stock"}, headers=tech)
    assert back.status_code == 409 and back.json()["code"] == "sleeper_discarded"


async def test_detail_not_found(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.get(f"/dormentes/{uuid.uuid4()}", headers=admin_headers)
    assert resp.status_code == 404
    hist = await client.get(f"/dormentes/{uuid.uuid4()}/historico", headers=admin_headers)
    assert hist.status_code == 404
