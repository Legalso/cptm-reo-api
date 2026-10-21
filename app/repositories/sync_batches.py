"""Consultas de lotes de sincronização."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_batch import SyncBatch


async def get_latest(
    session: AsyncSession, user_id: uuid.UUID, device_id: str | None
) -> SyncBatch | None:
    stmt = select(SyncBatch).where(SyncBatch.user_id == user_id)
    if device_id is not None:
        stmt = stmt.where(SyncBatch.device_id == device_id)
    stmt = stmt.order_by(SyncBatch.received_at.desc()).limit(1)
    return await session.scalar(stmt)
