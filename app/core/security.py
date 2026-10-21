"""Hash de senha (Argon2) e tokens JWT (access, refresh e convite)."""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.models.enums import Role

_password_hash = PasswordHash((Argon2Hasher(),))
# Hash fixo usado quando o login não existe: mantém o tempo de resposta parecido
# com o de senha errada e não revela quais usuários existem.
_DUMMY_HASH = _password_hash.hash("senha-inexistente-para-timing")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    INVITE = "invite"


def hash_password(password: str) -> str:
    """Gera hash Argon2 (com sal) — a senha em claro nunca é persistida."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Confere senha contra o hash; sem hash, gasta o mesmo tempo e falha."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    return _password_hash.verify(password, password_hash)


def _encode(claims: dict[str, Any], lifetime: timedelta) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + lifetime
    payload = {**claims, "iat": now, "exp": expires_at, "jti": uuid.uuid4().hex}
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, expires_at


def create_access_token(user_id: uuid.UUID, role: Role) -> tuple[str, datetime]:
    """Token curto (15 min por padrão) enviado em `Authorization: Bearer`."""
    minutes = get_settings().jwt_access_minutes
    claims = {"sub": str(user_id), "role": role.value, "type": TokenType.ACCESS.value}
    return _encode(claims, timedelta(minutes=minutes))


def create_refresh_token(user_id: uuid.UUID, role: Role) -> tuple[str, datetime]:
    """Token longo (7 dias) que só serve para obter um novo par em `/auth/refresh`."""
    days = get_settings().jwt_refresh_days
    claims = {"sub": str(user_id), "role": role.value, "type": TokenType.REFRESH.value}
    return _encode(claims, timedelta(days=days))


def create_invite_token(
    *, email: str, name: str, role: Role, registration: str | None
) -> tuple[str, datetime]:
    """Convite assinado e autocontido (sem tabela): vale `INVITE_TOKEN_HOURS`.

    Reaproveitar o token não duplica conta: o e-mail é único no banco.
    """
    hours = get_settings().invite_token_hours
    claims = {
        "sub": email,
        "name": name,
        "role": role.value,
        "registration": registration,
        "type": TokenType.INVITE.value,
    }
    return _encode(claims, timedelta(hours=hours))


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Valida assinatura, expiração e tipo; qualquer falha vira 401."""
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "type", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token expirado.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Token inválido.", code="invalid_token") from exc
    if payload.get("type") != expected_type.value:
        raise UnauthorizedError("Tipo de token incorreto.", code="invalid_token")
    return payload
