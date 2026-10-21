"""Consultas de ocorrências."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.occurrence import Occurrence


async def get_by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> Occurrence | None:
    return await session.scalar(select(Occurrence).where(Occurrence.client_uuid == client_uuid))


async def list_by_sleeper(session: AsyncSession, sleeper_id: uuid.UUID) -> list[Occurrence]:
    stmt = (
        select(Occurrence)
        .where(Occurrence.sleeper_id == sleeper_id)
        .order_by(Occurrence.occurred_at)
    )
    return list((await session.scalars(stmt)).all())
