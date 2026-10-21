"""Consultas de usuários."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.user import User
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_by_registration(session: AsyncSession, registration: str) -> User | None:
    return await session.scalar(select(User).where(User.registration == registration))


async def list_users(
    session: AsyncSession,
    page: PageParams,
    *,
    role: Role | None = None,
    active: bool | None = None,
    search: str | None = None,
) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.name, User.id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if active is not None:
        stmt = stmt.where(User.active == active)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.registration.ilike(pattern),
            )
        )
    return await paginate(session, stmt, page)


async def count_active_admins(session: AsyncSession) -> int:
    stmt = select(func.count()).where(User.role == Role.ADMIN, User.active.is_(True))
    return await session.scalar(stmt) or 0
