"""Consultas de movimentações."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movement import Movement


async def get_by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> Movement | None:
    return await session.scalar(select(Movement).where(Movement.client_uuid == client_uuid))


async def list_by_sleeper(session: AsyncSession, sleeper_id: uuid.UUID) -> list[Movement]:
    stmt = select(Movement).where(Movement.sleeper_id == sleeper_id).order_by(Movement.occurred_at)
    return list((await session.scalars(stmt)).all())
