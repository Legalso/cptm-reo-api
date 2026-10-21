"""Autenticação: login, refresh, usuário atual, aceite de convite e stubs de MFA."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.api.responses import errors
from app.core.errors import FeatureNotImplementedError
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import InviteAccept, UserRead
from app.services import auth as auth_service
from app.services import users as users_service

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login com matrícula ou e-mail",
    responses=errors(401, 422),
)
async def login(data: LoginRequest, session: SessionDep) -> TokenResponse:
    """Fase 1 devolve os tokens direto. Fase 2 devolverá `tempToken` para o MFA."""
    return await auth_service.authenticate(session, data.login, data.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar tokens com o refresh token",
    responses=errors(401, 422),
)
async def refresh(data: RefreshRequest, session: SessionDep) -> TokenResponse:
    return await auth_service.refresh(session, data.refresh_token)


@router.get("/me", response_model=UserRead, summary="Usuário logado", responses=errors(401))
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post(
    "/convite/aceitar",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aceitar convite e criar a conta",
    responses=errors(401, 409, 422),
)
async def accept_invite(data: InviteAccept, session: SessionDep) -> TokenResponse:
    """Público por natureza: o próprio token de convite é a autorização."""
    return await users_service.accept_invite(session, data)


@router.post(
    "/mfa",
    summary="Segundo fator online (fase 2)",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=errors(501),
)
async def mfa() -> None:
    # TODO(decidir): TOTP (app autenticador) x código por e-mail.
    raise FeatureNotImplementedError("MFA será implementado na fase 2.")


@router.post(
    "/mfa-offline",
    summary="Credencial offline de 48h (fase 2)",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    responses=errors(501),
)
async def mfa_offline() -> None:
    # TODO(decidir): formato e revogação da credencial offline de 48h.
    raise FeatureNotImplementedError("Credencial offline será implementada na fase 2.")
