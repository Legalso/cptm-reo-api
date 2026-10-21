"""Dependências compartilhadas pelas rotas (sessão, usuário atual, papéis)."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError, UnprocessableError
from app.core.security import TokenType, decode_token
from app.db.engine import SessionFactory
from app.models.enums import Role
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.common import PageParams, Period


async def get_session() -> AsyncIterator[AsyncSession]:
    """Uma sessão por requisição; os services decidem quando fazer commit."""
    async with SessionFactory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False: a ausência do header vira nosso 401 padrão, não o 403 do FastAPI.
_bearer = HTTPBearer(auto_error=False, description="Access token de `POST /auth/login`")


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve o usuário do access token; papel e status vêm do banco (fonte da verdade)."""
    if credentials is None:
        raise UnauthorizedError("Envie o header Authorization: Bearer <token>.")
    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise UnauthorizedError("Token inválido.", code="invalid_token") from exc
    user = await user_repo.get_by_id(session, user_id)
    if user is None or not user.active:
        raise UnauthorizedError("Usuário inexistente ou inativo.", code="inactive_user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], Awaitable[User]]:
    """Dependência que exige um dos papéis informados (admin sempre passa)."""
    allowed = frozenset(roles) | {Role.ADMIN}

    async def _checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError()
        return user

    return _checker


def page_params(
    limit: Annotated[int, Query(ge=1, le=200, description="Itens por página")] = 50,
    offset: Annotated[int, Query(ge=0, description="Itens a pular")] = 0,
) -> PageParams:
    """Paginação padrão (`limit` 50, máx. 200)."""
    return PageParams(limit=limit, offset=offset)


PageDep = Annotated[PageParams, Depends(page_params)]


def period_params(
    de: Annotated[
        datetime | None, Query(description="Início (ISO 8601, inclusivo; sem fuso = UTC)")
    ] = None,
    ate: Annotated[
        datetime | None, Query(description="Fim (ISO 8601, exclusivo; sem fuso = UTC)")
    ] = None,
) -> Period:
    """Filtro de período `?de=&ate=` usado nas listagens e indicadores."""
    start = _as_utc(de) if de else None
    end = _as_utc(ate) if ate else None
    if start and end and start >= end:
        raise UnprocessableError("'de' precisa ser anterior a 'ate'.", code="invalid_period")
    return Period(start=start, end=end)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


PeriodDep = Annotated[Period, Depends(period_params)]
