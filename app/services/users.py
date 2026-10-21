"""Gestão de usuários, papéis e convites."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableError,
)
from app.core.security import TokenType, create_invite_token, decode_token, hash_password
from app.models.enums import Role
from app.models.user import User
from app.repositories import users as user_repo
from app.schemas.auth import TokenResponse
from app.schemas.common import PageParams
from app.schemas.user import InviteAccept, InviteCreate, InviteRead, RoleUpdate, UserCreate
from app.services import audit
from app.services.auth import issue_tokens


def _normalize(email: str, registration: str | None) -> tuple[str, str | None]:
    """E-mail em minúsculas e matrícula em maiúsculas: login não depende de caixa."""
    return email.strip().lower(), registration.strip().upper() if registration else None


async def _ensure_available(session: AsyncSession, email: str, registration: str | None) -> None:
    if await user_repo.get_by_email(session, email):
        raise ConflictError("E-mail já cadastrado.", code="email_taken")
    if registration and await user_repo.get_by_registration(session, registration):
        raise ConflictError("Matrícula já cadastrada.", code="registration_taken")


async def list_users(
    session: AsyncSession,
    page: PageParams,
    *,
    role: Role | None,
    active: bool | None,
    search: str | None,
) -> tuple[list[User], int]:
    """Lista paginada com filtros por papel, status e texto."""
    return await user_repo.list_users(session, page, role=role, active=active, search=search)


async def _insert_user(
    session: AsyncSession,
    *,
    name: str,
    email: str,
    registration: str,
    password: str,
    role: Role,
    actor_id: uuid.UUID | None,
    action: str,
) -> User:
    user = User(
        name=name.strip(),
        email=email,
        registration=registration,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    await audit.record(
        session,
        actor_id=actor_id or user.id,
        action=action,
        entity="user",
        entity_id=user.id,
        after=audit.snapshot(user),
    )
    return user


async def create_user(session: AsyncSession, data: UserCreate, actor: User) -> User:
    """Cadastro direto pelo admin."""
    email, registration = _normalize(data.email, data.registration)
    assert registration is not None
    await _ensure_available(session, email, registration)
    user = await _insert_user(
        session,
        name=data.name,
        email=email,
        registration=registration,
        password=data.password,
        role=data.role,
        actor_id=actor.id,
        action="create",
    )
    await session.commit()
    return user


async def change_role(
    session: AsyncSession, user_id: uuid.UUID, data: RoleUpdate, actor: User
) -> User:
    """Troca o papel; impede remover o último admin ativo (sistema ficaria sem gestão)."""
    user = await user_repo.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    if user.role == data.role:
        return user
    if (
        user.role == Role.ADMIN
        and user.active
        and await user_repo.count_active_admins(session) <= 1
    ):
        raise BusinessRuleError("Não é possível rebaixar o último admin ativo.", code="last_admin")
    before = audit.snapshot(user)
    user.role = data.role
    await session.flush()
    await audit.record(
        session,
        actor_id=actor.id,
        action="change_role",
        entity="user",
        entity_id=user.id,
        before=before,
        after=audit.snapshot(user),
    )
    await session.commit()
    return user


async def create_invite(session: AsyncSession, data: InviteCreate, actor: User) -> InviteRead:
    """Gera token assinado + link; o envio (mailto) fica com o site.

    TODO(decidir): envio real de e-mail (provedor ainda não definido).
    """
    email, registration = _normalize(data.email, data.registration)
    await _ensure_available(session, email, registration)
    token, expires_at = create_invite_token(
        email=email, name=data.name.strip(), role=data.role, registration=registration
    )
    link = f"{get_settings().invite_base_url.rstrip('/')}/convite/{token}"
    await audit.record(
        session,
        actor_id=actor.id,
        action="invite",
        entity="user",
        entity_id=None,
        after={"email": email, "name": data.name, "role": data.role.value},
    )
    await session.commit()
    return InviteRead(
        email=email, name=data.name, role=data.role, token=token, link=link, expires_at=expires_at
    )


async def accept_invite(session: AsyncSession, data: InviteAccept) -> TokenResponse:
    """Cria a conta a partir do convite e já devolve os tokens (login automático)."""
    payload = decode_token(data.token, TokenType.INVITE)
    try:
        role = Role(payload["role"])
        email, registration = _normalize(
            payload["sub"], data.registration or payload.get("registration")
        )
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Convite inválido.", code="invalid_token") from exc
    if registration is None:
        raise UnprocessableError(
            "Informe a matrícula: o convite não trouxe uma.", code="registration_required"
        )
    await _ensure_available(session, email, registration)
    user = await _insert_user(
        session,
        name=str(payload.get("name") or email),
        email=email,
        registration=registration,
        password=data.password,
        role=role,
        actor_id=None,
        action="invite_accept",
    )
    await session.commit()
    return issue_tokens(user)
