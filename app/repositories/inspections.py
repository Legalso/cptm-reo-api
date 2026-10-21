"""Consultas de inspeções."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspection import Inspection


async def get_by_id(session: AsyncSession, inspection_id: uuid.UUID) -> Inspection | None:
    return await session.get(Inspection, inspection_id)


async def get_by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> Inspection | None:
    return await session.scalar(select(Inspection).where(Inspection.client_uuid == client_uuid))


async def list_by_sleeper(session: AsyncSession, sleeper_id: uuid.UUID) -> list[Inspection]:
    stmt = (
        select(Inspection)
        .where(Inspection.sleeper_id == sleeper_id)
        .order_by(Inspection.inspected_at)
    )
    return list((await session.scalars(stmt)).all())
