"""Indicadores e logs."""

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.enums import Role, SleeperStatus
from tests.conftest import Catalog, SleeperFactory, UserFactory, auth_headers


async def test_indicators_aggregate_period(
    client: AsyncClient, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    s1 = await make_sleeper()
    s2 = await make_sleeper()
    await make_sleeper(status=SleeperStatus.IN_TRACK)
    yesterday = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)

    await client.post(
        "/estoque/movimentacao",
        json={
            "sleeper_id": str(s1.id),
            "kind": "withdrawal",
            "requisition_number": "RM-1",
            "occurred_at": yesterday.isoformat(),
        },
        headers=tech,
    )
    for sleeper, result, seconds in ((s2, "rejected", 100), (s2, "approved", 50)):
        await client.post(
            "/inspecoes",
            json={
                "sleeper_id": str(sleeper.id),
                "conservation": "fair",
                "has_cracks": False,
                "biological_attack": False,
                "moisture": "dry",
                "result": result,
                "duration_seconds": seconds,
            },
            headers=tech,
        )
    await client.post(
        "/estoque/ocorrencias",
        json={"location_id": str(catalog.street.id), "kind": "loss", "description": "Sumiu um"},
        headers=tech,
    )

    resp = await client.get("/indicadores", headers=supervisor)

    assert resp.status_code == 200
    body = resp.json()
    statuses = {s["status"]: s["count"] for s in body["sleepers_by_status"]}
    assert statuses == {
        "in_stock": 1,
        "withdrawn": 1,
        "in_track": 1,
        "quarantine": 0,
        "discarded": 0,
    }
    assert body["sleepers_total"] == 3
    assert len(body["movements_per_day"]) == 8  # 7 dias tocam 8 datas UTC
    assert sum(d["withdrawal"] for d in body["movements_per_day"]) == 1
    assert body["inspections_total"] == 2
    assert body["average_inspection_seconds"] == 75
    assert body["rejection_rate"] == 0.5
    assert body["losses"] == 1
    assert body["sleepers_by_location"][0]["name"] == "Rua 08"
    assert body["sleepers_by_species"][0]["code"] == "13"


async def test_indicators_period_and_permissions(
    client: AsyncClient, make_user: UserFactory
) -> None:
    assert (await client.get("/indicadores")).status_code == 401
    operator = auth_headers(await make_user(Role.OPERATOR))
    assert (await client.get("/indicadores", headers=operator)).status_code == 403
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    custom = await client.get(
        "/indicadores",
        params={"de": "2026-10-01T00:00:00Z", "ate": "2026-10-03T00:00:00Z"},
        headers=supervisor,
    )
    assert [d["day"] for d in custom.json()["movements_per_day"]] == ["2026-10-01", "2026-10-02"]
    too_long = await client.get(
        "/indicadores",
        params={"de": "2024-01-01T00:00:00Z", "ate": "2026-01-01T00:00:00Z"},
        headers=supervisor,
    )
    assert too_long.status_code == 422 and too_long.json()["code"] == "period_too_long"
    bad = await client.get("/indicadores", params={"de": "ontem"}, headers=supervisor)
    assert bad.status_code == 422


async def test_logs_list_and_filter(
    client: AsyncClient, make_user: UserFactory, admin: object, admin_headers: dict[str, str]
) -> None:
    target = await make_user()
    await client.patch(
        f"/usuarios/{target.id}/papel", json={"role": "tecnico"}, headers=admin_headers
    )

    resp = await client.get(
        "/logs", params={"entity": "user", "action": "change_role"}, headers=admin_headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    log = body["items"][0]
    assert log["entity_id"] == str(target.id)
    assert log["before"]["role"] == "operador" and log["after"]["role"] == "tecnico"
    assert log["user"]["id"] == str(admin.id)  # type: ignore[attr-defined]
    assert "password_hash" not in log["after"]

    by_entity = await client.get(
        "/logs", params={"entity_id": str(uuid.uuid4())}, headers=admin_headers
    )
    assert by_entity.json()["total"] == 0


async def test_logs_permissions_and_validation(client: AsyncClient, make_user: UserFactory) -> None:
    assert (await client.get("/logs")).status_code == 401
    tech = auth_headers(await make_user(Role.TECHNICIAN))
    assert (await client.get("/logs", headers=tech)).status_code == 403
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    assert (await client.get("/logs", headers=supervisor)).status_code == 200
    bad = await client.get("/logs", params={"user_id": "nao-e-uuid"}, headers=supervisor)
    assert bad.status_code == 422
