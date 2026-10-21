import uuid

from httpx import AsyncClient

from app.models.enums import Role
from tests.conftest import Catalog, SleeperFactory, UserFactory, auth_headers


async def test_replicate_and_status(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    headers = auth_headers(await make_user())
    sleeper = await make_sleeper()
    body = {
        "device_id": "coletor-07",
        "movements": [
            {
                "client_uuid": str(uuid.uuid4()),
                "rfid_tag": sleeper.rfid_tag,
                "kind": "transfer",
                "to_location_id": str(catalog.other_street.id),
            }
        ],
    }

    empty = await client.get("/sincronizacao/status", headers=headers)
    assert empty.status_code == 200 and empty.json()["last_batch"] is None

    resp = await client.post("/sincronizacao/replicar", json=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1 and resp.json()["status"] == "completed"

    status = await client.get(
        "/sincronizacao/status", params={"device_id": "coletor-07"}, headers=headers
    )
    assert status.json()["last_batch"]["id"] == resp.json()["id"]
    other_device = await client.get(
        "/sincronizacao/status", params={"device_id": "outro"}, headers=headers
    )
    assert other_device.json()["last_batch"] is None


async def test_replicate_auth_roles_and_validation(
    client: AsyncClient, make_user: UserFactory
) -> None:
    assert (await client.post("/sincronizacao/replicar", json={})).status_code == 401
    assert (await client.get("/sincronizacao/status")).status_code == 401
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    forbidden = await client.post("/sincronizacao/replicar", json={}, headers=supervisor)
    assert forbidden.status_code == 403

    operator = auth_headers(await make_user())
    not_a_list = await client.post(
        "/sincronizacao/replicar", json={"movements": "x"}, headers=operator
    )
    assert not_a_list.status_code == 422
    too_big = await client.post(
        "/sincronizacao/replicar", json={"movements": [{}] * 1001}, headers=operator
    )
    assert too_big.status_code == 422
