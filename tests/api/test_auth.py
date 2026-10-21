from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import TokenType, _encode, create_refresh_token
from app.models.enums import Role
from tests.conftest import DEFAULT_PASSWORD, UserFactory, auth_headers


@pytest.mark.parametrize("by", ["registration", "email"])
async def test_login_by_registration_or_email(
    client: AsyncClient, make_user: UserFactory, by: str
) -> None:
    user = await make_user(Role.TECHNICIAN)
    login = user.registration.lower() if by == "registration" else user.email.upper()

    resp = await client.post("/auth/login", json={"login": login, "password": DEFAULT_PASSWORD})

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == str(user.id)
    assert "password_hash" not in body["user"]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "tecnico"


async def test_login_accepts_portuguese_field_names(
    client: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user()
    resp = await client.post("/auth/login", json={"usuario": user.email, "senha": DEFAULT_PASSWORD})
    assert resp.status_code == 200


@pytest.mark.parametrize("case", ["wrong_password", "unknown", "inactive"])
async def test_login_rejects_with_same_message(
    client: AsyncClient, make_user: UserFactory, case: str
) -> None:
    user = await make_user(active=case != "inactive")
    login = "ninguem@reo.local" if case == "unknown" else user.email
    password = "errada-123" if case == "wrong_password" else DEFAULT_PASSWORD

    resp = await client.post("/auth/login", json={"login": login, "password": password})

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Login ou senha inválidos.", "code": "invalid_credentials"}


async def test_login_validation_error(client: AsyncClient) -> None:
    resp = await client.post("/auth/login", json={"login": "x"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


async def test_refresh_issues_new_pair(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user()
    refresh, _ = create_refresh_token(user.id, user.role)

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == str(user.id)


async def test_refresh_rejects_access_token(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user()
    access = auth_headers(user)["Authorization"].removeprefix("Bearer ")
    resp = await client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_token"


async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "unauthorized"
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_expired_token(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user()
    token, _ = _encode(
        {"sub": str(user.id), "role": user.role.value, "type": TokenType.ACCESS.value},
        timedelta(seconds=-1),
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "token_expired"


async def test_me_rejects_deactivated_user(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(active=False)
    resp = await client.get("/auth/me", headers=auth_headers(user))
    assert resp.status_code == 401


@pytest.mark.parametrize("path", ["/auth/mfa", "/auth/mfa-offline"])
async def test_mfa_stubs_return_501(client: AsyncClient, path: str) -> None:
    resp = await client.post(path, json={})
    assert resp.status_code == 501
    assert resp.json()["code"] == "not_implemented"
