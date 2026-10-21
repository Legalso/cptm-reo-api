"""Consultas de inspeções."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InspectionResult
from app.models.inspection import Inspection
from app.repositories.base import paginate
from app.schemas.common import PageParams


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


async def list_inspections(
    session: AsyncSession,
    page: PageParams,
    *,
    sleeper_id: uuid.UUID | None,
    result: InspectionResult | None,
    inspector_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[Inspection], int]:
    stmt = select(Inspection).order_by(Inspection.inspected_at.desc(), Inspection.id)
    if sleeper_id is not None:
        stmt = stmt.where(Inspection.sleeper_id == sleeper_id)
    if result is not None:
        stmt = stmt.where(Inspection.result == result)
    if inspector_id is not None:
        stmt = stmt.where(Inspection.inspector_id == inspector_id)
    if start is not None:
        stmt = stmt.where(Inspection.inspected_at >= start)
    if end is not None:
        stmt = stmt.where(Inspection.inspected_at < end)
    return await paginate(session, stmt, page)
