"""Gestão de usuários (admin) e consulta (admin, supervisor)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import PageDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ADMIN_ONLY, MANAGEMENT_ROLES
from app.models.enums import Role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import InviteCreate, InviteRead, RoleUpdate, UserCreate, UserRead
from app.services import users as users_service

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

Admin = Annotated[User, Depends(require_roles(*ADMIN_ONLY))]
Manager = Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))]


@router.get("", response_model=Page[UserRead], summary="Listar usuários", responses=AUTH)
async def list_users(
    session: SessionDep,
    _: Manager,
    page: PageDep,
    role: Annotated[Role | None, Query(description="Filtra por papel")] = None,
    active: Annotated[bool | None, Query(description="Filtra por ativo/inativo")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Nome, e-mail ou matrícula")] = None,
) -> Page[UserRead]:
    items, total = await users_service.list_users(session, page, role=role, active=active, search=q)
    return Page(
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    responses={**AUTH_VALIDATION, **errors(409)},
)
async def create_user(data: UserCreate, session: SessionDep, actor: Admin) -> UserRead:
    return UserRead.model_validate(await users_service.create_user(session, data, actor))


@router.patch(
    "/{user_id}/papel",
    response_model=UserRead,
    summary="Alterar papel do usuário",
    responses={**AUTH_VALIDATION, **errors(404, 409)},
)
async def change_role(
    user_id: uuid.UUID, data: RoleUpdate, session: SessionDep, actor: Admin
) -> UserRead:
    return UserRead.model_validate(await users_service.change_role(session, user_id, data, actor))


@router.post(
    "/convite",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar convite (token + link, sem envio de e-mail)",
    responses={**AUTH_VALIDATION, **errors(409)},
)
async def create_invite(data: InviteCreate, session: SessionDep, actor: Admin) -> InviteRead:
    """O site usa o `link` devolvido para abrir o mailto. Validade: `INVITE_TOKEN_HOURS`."""
    return await users_service.create_invite(session, data, actor)
