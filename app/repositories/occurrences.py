"""Consultas de ocorrências."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OccurrenceKind
from app.models.occurrence import Occurrence
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_client_uuid(session: AsyncSession, client_uuid: uuid.UUID) -> Occurrence | None:
    return await session.scalar(select(Occurrence).where(Occurrence.client_uuid == client_uuid))


async def list_by_sleeper(session: AsyncSession, sleeper_id: uuid.UUID) -> list[Occurrence]:
    stmt = (
        select(Occurrence)
        .where(Occurrence.sleeper_id == sleeper_id)
        .order_by(Occurrence.occurred_at)
    )
    return list((await session.scalars(stmt)).all())


async def list_occurrences(
    session: AsyncSession,
    page: PageParams,
    *,
    kind: OccurrenceKind | None,
    location_id: uuid.UUID | None,
    sleeper_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[Occurrence], int]:
    stmt = select(Occurrence).order_by(Occurrence.occurred_at.desc(), Occurrence.id)
    if kind is not None:
        stmt = stmt.where(Occurrence.kind == kind)
    if location_id is not None:
        stmt = stmt.where(Occurrence.location_id == location_id)
    if sleeper_id is not None:
        stmt = stmt.where(Occurrence.sleeper_id == sleeper_id)
    if start is not None:
        stmt = stmt.where(Occurrence.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(Occurrence.occurred_at < end)
    return await paginate(session, stmt, page)
