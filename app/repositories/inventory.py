"""Consultas de contagens de inventário."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryCount
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_client_uuid(
    session: AsyncSession, client_uuid: uuid.UUID
) -> InventoryCount | None:
    return await session.scalar(
        select(InventoryCount).where(InventoryCount.client_uuid == client_uuid)
    )


async def list_counts(
    session: AsyncSession,
    page: PageParams,
    *,
    location_id: uuid.UUID | None,
    species_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[InventoryCount], int]:
    stmt = select(InventoryCount).order_by(InventoryCount.counted_at.desc(), InventoryCount.id)
    if location_id is not None:
        stmt = stmt.where(InventoryCount.location_id == location_id)
    if species_id is not None:
        stmt = stmt.where(InventoryCount.species_id == species_id)
    if start is not None:
        stmt = stmt.where(InventoryCount.counted_at >= start)
    if end is not None:
        stmt = stmt.where(InventoryCount.counted_at < end)
    return await paginate(session, stmt, page)
