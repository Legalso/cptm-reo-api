"""Agregações do dashboard — todas feitas no banco (GROUP BY / FILTER)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, Row, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    InspectionResult,
    LocationKind,
    MovementKind,
    OccurrenceKind,
    SleeperStatus,
)
from app.models.inspection import Inspection
from app.models.location import Location
from app.models.movement import Movement
from app.models.occurrence import Occurrence
from app.models.sleeper import Sleeper
from app.models.species import WoodSpecies


def _utc_day(column: Any) -> Any:
    """Dia (UTC) de uma coluna timestamptz, independente do fuso da sessão."""
    return cast(func.timezone("UTC", column), Date)


async def sleepers_by_status(session: AsyncSession) -> dict[SleeperStatus, int]:
    stmt = select(Sleeper.status, func.count()).group_by(Sleeper.status)
    return {status: count for status, count in (await session.execute(stmt)).all()}


async def sleepers_by_species(  # colunas da espécie vêm nulas p/ "sem espécie"
    session: AsyncSession,
) -> list[Row[uuid.UUID, str, str | None, str | None, int]]:
    stmt = (
        select(
            WoodSpecies.id,
            WoodSpecies.code,
            WoodSpecies.scientific_name,
            WoodSpecies.common_name,
            func.count(Sleeper.id),
        )
        .select_from(Sleeper)
        .outerjoin(WoodSpecies, Sleeper.species_id == WoodSpecies.id)
        .where(Sleeper.status != SleeperStatus.DISCARDED)
        .group_by(WoodSpecies.id)
        .order_by(func.count(Sleeper.id).desc())
    )
    return list((await session.execute(stmt)).all())


async def sleepers_by_location(
    session: AsyncSession,
) -> list[Row[uuid.UUID, str, LocationKind, int]]:
    """Só quem está no pátio (com local atual)."""
    stmt = (
        select(Location.id, Location.name, Location.kind, func.count(Sleeper.id))
        .join(Sleeper, Sleeper.current_location_id == Location.id)
        .group_by(Location.id)
        .order_by(func.count(Sleeper.id).desc())
    )
    return list((await session.execute(stmt)).all())


async def movements_per_day(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[date, dict[MovementKind, int]]:
    day = _utc_day(Movement.occurred_at)
    stmt = (
        select(
            day,
            *(func.count().filter(Movement.kind == kind) for kind in MovementKind),
        )
        .where(Movement.occurred_at >= start, Movement.occurred_at < end)
        .group_by(day)
    )
    return {
        row[0]: dict(zip(MovementKind, row[1:], strict=True))
        for row in (await session.execute(stmt)).all()
    }


async def inspections_per_day(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[date, tuple[int, int]]:
    """(aprovadas, reprovadas) por dia."""
    day = _utc_day(Inspection.inspected_at)
    stmt = (
        select(
            day,
            func.count().filter(Inspection.result == InspectionResult.APPROVED),
            func.count().filter(Inspection.result == InspectionResult.REJECTED),
        )
        .where(Inspection.inspected_at >= start, Inspection.inspected_at < end)
        .group_by(day)
    )
    return {row[0]: (row[1], row[2]) for row in (await session.execute(stmt)).all()}


async def inspection_summary(
    session: AsyncSession, start: datetime, end: datetime
) -> tuple[int, int, float | None]:
    """(total, reprovadas, duração média em segundos) no período."""
    stmt = select(
        func.count(),
        func.count().filter(Inspection.result == InspectionResult.REJECTED),
        func.avg(Inspection.duration_seconds),
    ).where(Inspection.inspected_at >= start, Inspection.inspected_at < end)
    total, rejected, avg = (await session.execute(stmt)).one()
    return total, rejected, float(avg) if avg is not None else None


async def occurrences_by_kind(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[OccurrenceKind, int]:
    stmt = (
        select(Occurrence.kind, func.count())
        .where(Occurrence.occurred_at >= start, Occurrence.occurred_at < end)
        .group_by(Occurrence.kind)
    )
    return {kind: count for kind, count in (await session.execute(stmt)).all()}
