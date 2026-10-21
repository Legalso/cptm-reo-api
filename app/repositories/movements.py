"""Consultas de movimentações."""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MovementKind
from app.models.movement import Movement
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> Movement | None:
    return await session.scalar(select(Movement).where(Movement.client_uuid == client_uuid))


async def list_by_sleeper(session: AsyncSession, sleeper_id: uuid.UUID) -> list[Movement]:
    stmt = select(Movement).where(Movement.sleeper_id == sleeper_id).order_by(Movement.occurred_at)
    return list((await session.scalars(stmt)).all())


async def list_movements(
    session: AsyncSession,
    page: PageParams,
    *,
    sleeper_id: uuid.UUID | None,
    kind: MovementKind | None,
    location_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[Movement], int]:
    stmt = select(Movement).order_by(Movement.occurred_at.desc(), Movement.id)
    if sleeper_id is not None:
        stmt = stmt.where(Movement.sleeper_id == sleeper_id)
    if kind is not None:
        stmt = stmt.where(Movement.kind == kind)
    if location_id is not None:
        stmt = stmt.where(
            or_(Movement.from_location_id == location_id, Movement.to_location_id == location_id)
        )
    if user_id is not None:
        stmt = stmt.where(Movement.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Movement.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Movement.occurred_at < end)
    return await paginate(session, stmt, page)
