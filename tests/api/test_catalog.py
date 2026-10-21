"""Espécies e locais."""

from httpx import AsyncClient

from app.models.enums import Role
from tests.conftest import Catalog, UserFactory, auth_headers


async def test_species_crud_by_specialist(client: AsyncClient, make_user: UserFactory) -> None:
    headers = auth_headers(await make_user(Role.SPECIALIST))

    created = await client.post(
        "/especies", json={"code": "23", "scientific_name": "Manilkara huberi"}, headers=headers
    )
    assert created.status_code == 201
    species_id = created.json()["id"]

    patched = await client.patch(
        f"/especies/{species_id}", json={"common_name": "Maçaranduba"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["common_name"] == "Maçaranduba"

    listing = await client.get("/especies", params={"q": "manilkara"}, headers=headers)
    assert listing.json()["total"] == 1
    detail = await client.get(f"/especies/{species_id}", headers=headers)
    assert detail.json()["code"] == "23"


async def test_species_validation_and_conflict(
    client: AsyncClient, admin_headers: dict[str, str], catalog: Catalog
) -> None:
    no_name = await client.post("/especies", json={"code": "99"}, headers=admin_headers)
    assert no_name.status_code == 422
    dup = await client.post(
        "/especies", json={"code": "13", "common_name": "x"}, headers=admin_headers
    )
    assert dup.status_code == 409
    clear_all = await client.patch(
        f"/especies/{catalog.species.id}", json={"scientific_name": None}, headers=admin_headers
    )
    assert clear_all.status_code == 422


async def test_species_permissions(client: AsyncClient, make_user: UserFactory) -> None:
    assert (await client.get("/especies")).status_code == 401
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    assert (await client.get("/especies", headers=tech)).status_code == 200
    resp = await client.post("/especies", json={"code": "30", "common_name": "x"}, headers=tech)
    assert resp.status_code == 403


async def test_location_hierarchy(client: AsyncClient, make_user: UserFactory) -> None:
    headers = auth_headers(await make_user(Role.SUPERVISOR))

    yard = await client.post(
        "/locais", json={"name": "Pátio Lapa", "kind": "warehouse"}, headers=headers
    )
    assert yard.status_code == 201
    yard_id = yard.json()["id"]

    street = await client.post(
        "/locais",
        json={"name": "Rua 01", "kind": "street", "parent_id": yard_id, "latitude": -23.5},
        headers=headers,
    )
    assert street.status_code == 201

    dup = await client.post(
        "/locais", json={"name": "Rua 01", "kind": "street", "parent_id": yard_id}, headers=headers
    )
    assert dup.status_code == 409
    orphan = await client.post("/locais", json={"name": "Rua X", "kind": "street"}, headers=headers)
    assert orphan.status_code == 422
    nested = await client.post(
        "/locais",
        json={"name": "Sub", "kind": "street", "parent_id": street.json()["id"]},
        headers=headers,
    )
    assert nested.status_code == 422

    children = await client.get("/locais", params={"parent_id": yard_id}, headers=headers)
    assert [c["name"] for c in children.json()["items"]] == ["Rua 01"]

    off = await client.patch(
        f"/locais/{street.json()['id']}", json={"active": False}, headers=headers
    )
    assert off.status_code == 200 and off.json()["active"] is False


async def test_location_permissions_and_validation(
    client: AsyncClient, make_user: UserFactory, catalog: Catalog
) -> None:
    assert (await client.get("/locais")).status_code == 401
    operator = auth_headers(await make_user(Role.OPERATOR))
    assert (await client.get("/locais", headers=operator)).status_code == 200
    forbidden = await client.post(
        "/locais", json={"name": "P", "kind": "warehouse"}, headers=operator
    )
    assert forbidden.status_code == 403
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    bad_lat = await client.patch(
        f"/locais/{catalog.street.id}", json={"latitude": 200}, headers=supervisor
    )
    assert bad_lat.status_code == 422
    missing = await client.get("/locais/00000000-0000-0000-0000-000000000000", headers=supervisor)
    assert missing.status_code == 404
