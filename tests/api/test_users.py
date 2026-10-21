from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import Role
from app.models.user import User
from tests.conftest import UserFactory, auth_headers

NEW_USER = {
    "name": "Fernanda Rocha",
    "email": "Fernanda.Rocha@CPTM.sp.gov.br",
    "registration": "rl-9001",
    "password": "Senha-forte-123",
    "role": "Operador",
}


async def test_admin_creates_user_and_audits(
    client: AsyncClient, admin: User, admin_headers: dict[str, str], session: AsyncSession
) -> None:
    resp = await client.post("/usuarios", json=NEW_USER, headers=admin_headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "fernanda.rocha@cptm.sp.gov.br"
    assert body["registration"] == "RL-9001"
    assert body["role"] == "operador"
    assert "password" not in body and "password_hash" not in body
    log = await session.scalar(
        select(AuditLog).where(AuditLog.entity == "user", AuditLog.action == "create")
    )
    assert log is not None and log.user_id == admin.id
    assert log.after is not None and "password_hash" not in log.after


async def test_create_user_conflict_on_email(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    await client.post("/usuarios", json=NEW_USER, headers=admin_headers)
    resp = await client.post(
        "/usuarios", json={**NEW_USER, "registration": "RL-1"}, headers=admin_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "email_taken"


async def test_create_user_validation(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    resp = await client.post(
        "/usuarios", json={**NEW_USER, "role": "Analista"}, headers=admin_headers
    )
    assert resp.status_code == 422
    short = await client.post(
        "/usuarios", json={**NEW_USER, "password": "123"}, headers=admin_headers
    )
    assert short.status_code == 422


async def test_users_routes_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/usuarios")).status_code == 401
    assert (await client.post("/usuarios", json=NEW_USER)).status_code == 401
    assert (await client.post("/usuarios/convite", json={})).status_code == 401


async def test_users_routes_forbid_wrong_role(client: AsyncClient, make_user: UserFactory) -> None:
    operator = auth_headers(await make_user(Role.OPERATOR))
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))

    assert (await client.get("/usuarios", headers=operator)).status_code == 403
    assert (await client.post("/usuarios", json=NEW_USER, headers=supervisor)).status_code == 403
    invite = {"nome": "X", "email": "x@cptm.sp.gov.br", "papel": "operador"}
    assert (
        await client.post("/usuarios/convite", json=invite, headers=supervisor)
    ).status_code == 403


async def test_supervisor_lists_users_with_filters(
    client: AsyncClient, make_user: UserFactory
) -> None:
    supervisor = await make_user(Role.SUPERVISOR)
    tech = await make_user(Role.TECHNICIAN)

    resp = await client.get(
        "/usuarios", params={"role": "tecnico", "limit": 10}, headers=auth_headers(supervisor)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 10 and body["offset"] == 0
    assert [u["id"] for u in body["items"]] == [str(tech.id)]
    assert body["total"] == 1


async def test_list_users_rejects_limit_over_200(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    resp = await client.get("/usuarios", params={"limit": 201}, headers=admin_headers)
    assert resp.status_code == 422


async def test_change_role(
    client: AsyncClient, make_user: UserFactory, admin_headers: dict[str, str]
) -> None:
    user = await make_user(Role.OPERATOR)
    resp = await client.patch(
        f"/usuarios/{user.id}/papel", json={"papel": "Técnico"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "tecnico"


async def test_change_role_validation_and_not_found(
    client: AsyncClient, admin: User, admin_headers: dict[str, str]
) -> None:
    bad = await client.patch(
        f"/usuarios/{admin.id}/papel", json={"role": "chefe"}, headers=admin_headers
    )
    assert bad.status_code == 422
    missing = await client.patch(
        "/usuarios/00000000-0000-0000-0000-000000000000/papel",
        json={"role": "admin"},
        headers=admin_headers,
    )
    assert missing.status_code == 404


async def test_cannot_demote_last_admin(
    client: AsyncClient, admin: User, admin_headers: dict[str, str]
) -> None:
    resp = await client.patch(
        f"/usuarios/{admin.id}/papel", json={"role": "operador"}, headers=admin_headers
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "last_admin"


async def test_change_role_forbidden_for_supervisor(
    client: AsyncClient, make_user: UserFactory
) -> None:
    target = await make_user()
    supervisor = auth_headers(await make_user(Role.SUPERVISOR))
    resp = await client.patch(
        f"/usuarios/{target.id}/papel", json={"role": "admin"}, headers=supervisor
    )
    assert resp.status_code == 403


async def test_invite_flow_with_site_payload(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    # Corpo exatamente como o site (InviteSection) envia hoje.
    site_body = {
        "nome": "Marcos Vinícius",
        "email": "marcos@cptm.sp.gov.br",
        "papel": "Tecnico",
        "link": "https://qualquer/convite/abc",
    }
    resp = await client.post("/usuarios/convite", json=site_body, headers=admin_headers)

    assert resp.status_code == 201
    invite = resp.json()
    assert invite["role"] == "tecnico"
    assert invite["link"].endswith(f"/convite/{invite['token']}")

    accepted = await client.post(
        "/auth/convite/aceitar",
        json={"token": invite["token"], "senha": "Senha-forte-123", "matricula": "rl-77"},
    )
    assert accepted.status_code == 201
    assert accepted.json()["user"]["registration"] == "RL-77"
    assert accepted.json()["user"]["name"] == "Marcos Vinícius"

    again = await client.post(
        "/auth/convite/aceitar",
        json={"token": invite["token"], "password": "Senha-forte-123", "registration": "RL-78"},
    )
    assert again.status_code == 409


async def test_invite_rejects_unknown_role(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/usuarios/convite",
        json={"nome": "X", "email": "x@cptm.sp.gov.br", "papel": "Analista"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


async def test_accept_invite_requires_registration_and_valid_token(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    invite = (
        await client.post(
            "/usuarios/convite",
            json={"name": "Yara", "email": "yara@cptm.sp.gov.br", "role": "operador"},
            headers=admin_headers,
        )
    ).json()
    no_reg = await client.post(
        "/auth/convite/aceitar", json={"token": invite["token"], "password": "Senha-forte-123"}
    )
    assert no_reg.status_code == 422
    assert no_reg.json()["code"] == "registration_required"

    forged = await client.post(
        "/auth/convite/aceitar",
        json={"token": invite["token"] + "x", "password": "Senha-forte-123", "registration": "Y1"},
    )
    assert forged.status_code == 401
