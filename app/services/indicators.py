"""Indicadores do dashboard gerencial."""

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnprocessableError
from app.db.mixins import utcnow
from app.models.enums import MovementKind, OccurrenceKind, SleeperStatus
from app.repositories import indicators as repo
from app.schemas.common import Period
from app.schemas.indicators import (
    IndicatorsRead,
    InspectionsDay,
    LocationCount,
    MovementsDay,
    OccurrenceCount,
    PeriodRead,
    SpeciesCount,
    StatusCount,
)

DEFAULT_WINDOW = timedelta(days=7)
MAX_WINDOW = timedelta(days=366)


def resolve_period(period: Period) -> tuple[datetime, datetime]:
    """Padrão: últimos 7 dias até agora. Janela máxima de 1 ano (série diária)."""
    end = period.end or utcnow()
    start = period.start or end - DEFAULT_WINDOW
    if start >= end:
        raise UnprocessableError("'de' precisa ser anterior a 'ate'.", code="invalid_period")
    if end - start > MAX_WINDOW:
        raise UnprocessableError("Período máximo é de 366 dias.", code="period_too_long")
    return start, end


def _days(start: datetime, end: datetime) -> list[date]:
    """Todos os dias (UTC) tocados pelo período, para a série não ter buracos."""
    first, last = start.date(), (end - timedelta(microseconds=1)).date()
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


async def get_indicators(session: AsyncSession, period: Period) -> IndicatorsRead:
    start, end = resolve_period(period)
    by_status = await repo.sleepers_by_status(session)
    movements = await repo.movements_per_day(session, start, end)
    inspections = await repo.inspections_per_day(session, start, end)
    insp_total, insp_rejected, avg_seconds = await repo.inspection_summary(session, start, end)
    occurrences = await repo.occurrences_by_kind(session, start, end)
    days = _days(start, end)

    empty_moves = dict.fromkeys(MovementKind, 0)
    return IndicatorsRead(
        period=PeriodRead(start=start, end=end),
        sleepers_total=sum(by_status.values()),
        sleepers_by_status=[
            StatusCount(status=s, count=by_status.get(s, 0)) for s in SleeperStatus
        ],
        sleepers_by_species=[
            SpeciesCount(
                species_id=sid,
                code=code,
                name=scientific or common or "Sem espécie",
                count=count,
            )
            for sid, code, scientific, common, count in await repo.sleepers_by_species(session)
        ],
        sleepers_by_location=[
            LocationCount(location_id=lid, name=name, kind=kind, count=count)
            for lid, name, kind, count in await repo.sleepers_by_location(session)
        ],
        movements_per_day=[
            MovementsDay(
                day=day,
                entry=(m := movements.get(day, empty_moves))[MovementKind.ENTRY],
                withdrawal=m[MovementKind.WITHDRAWAL],
                transfer=m[MovementKind.TRANSFER],
                total=sum(m.values()),
            )
            for day in days
        ],
        inspections_per_day=[
            InspectionsDay(
                day=day,
                approved=(i := inspections.get(day, (0, 0)))[0],
                rejected=i[1],
                total=i[0] + i[1],
            )
            for day in days
        ],
        inspections_total=insp_total,
        average_inspection_seconds=avg_seconds,
        rejection_rate=(insp_rejected / insp_total) if insp_total else None,
        occurrences_by_kind=[
            OccurrenceCount(kind=k, count=occurrences.get(k, 0)) for k in OccurrenceKind
        ],
        losses=occurrences.get(OccurrenceKind.LOSS, 0),
    )
