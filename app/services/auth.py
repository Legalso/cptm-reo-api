"""Login, refresh e emissão de tokens."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead

logger = logging.getLogger(__name__)


def issue_tokens(user: User) -> TokenResponse:
    """Gera o par access/refresh para o usuário."""
    access, access_exp = create_access_token(user.id, user.role)
    refresh, refresh_exp = create_refresh_token(user.id, user.role)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_at=access_exp,
        refresh_expires_at=refresh_exp,
        user=UserRead.model_validate(user),
    )


async def find_by_login(session: AsyncSession, login: str) -> User | None:
    """Login com "@" é e-mail; sem "@" é matrícula."""
    login = login.strip()
    if "@" in login:
        return await user_repo.get_by_email(session, login.lower())
    return await user_repo.get_by_registration(session, login.upper())


async def authenticate(session: AsyncSession, login: str, password: str) -> TokenResponse:
    """Valida credenciais; a mesma mensagem para todo erro evita enumerar usuários."""
    user = await find_by_login(session, login)
    valid = verify_password(password, user.password_hash if user else None)
    if user is None or not valid or not user.active:
        logger.info("Falha de login")
        raise UnauthorizedError("Login ou senha inválidos.", code="invalid_credentials")
    # TODO(decidir): Fase 2 devolve tempToken e exige MFA (TOTP x e-mail ainda em aberto).
    return issue_tokens(user)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenResponse:
    """Troca um refresh válido por um par novo, relendo papel/status do banco."""
    payload = decode_token(refresh_token, TokenType.REFRESH)
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise UnauthorizedError("Token inválido.", code="invalid_token") from exc
    user = await user_repo.get_by_id(session, user_id)
    if user is None or not user.active:
        raise UnauthorizedError("Usuário inexistente ou inativo.", code="inactive_user")
    return issue_tokens(user)
