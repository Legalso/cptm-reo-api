"""Ocorrências de campo."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnprocessableError
from app.models.enums import OccurrenceKind
from app.models.occurrence import Occurrence
from app.models.user import User
from app.repositories import occurrences as occurrence_repo
from app.schemas.common import PageParams
from app.schemas.operations import OccurrenceCreate
from app.services import audit, clock
from app.services import locations as location_service
from app.services import sleepers as sleeper_service
from app.services.idempotency import commit_idempotent


async def apply_occurrence(
    session: AsyncSession, data: OccurrenceCreate, actor: User
) -> tuple[Occurrence, bool]:
    """Registra a ocorrência (sem commit). Sem `location_id`, usa o local atual do dormente.

    Ocorrência não muda o status do dormente: é um relato; quem decide é a inspeção.
    """
    if data.client_uuid:
        existing = await occurrence_repo.get_by_client_uuid(session, data.client_uuid)
        if existing is not None:
            return existing, False
    occurred_at = clock.resolve_occurred_at(data.occurred_at)
    sleeper_id: uuid.UUID | None = None
    location_id = data.location_id
    if data.sleeper_id or data.rfid_tag:
        sleeper = await sleeper_service.resolve_for_update(session, data.sleeper_id, data.rfid_tag)
        sleeper_id = sleeper.id
        location_id = location_id or sleeper.current_location_id
    if location_id is None:
        raise UnprocessableError(
            "Dormente fora do pátio: informe location_id.", code="location_required"
        )
    await location_service.get(session, location_id)
    occurrence = Occurrence(
        sleeper_id=sleeper_id,
        location_id=location_id,
        kind=data.kind,
        description=data.description.strip(),
        user_id=actor.id,
        occurred_at=occurred_at,
        client_uuid=data.client_uuid,
    )
    await audit.create_with_audit(session, occurrence, actor_id=actor.id, entity="occurrence")
    return occurrence, True


async def register_occurrence(
    session: AsyncSession, data: OccurrenceCreate, actor: User
) -> tuple[Occurrence, bool]:
    """`POST /estoque/ocorrencias`."""

    async def _find() -> Occurrence | None:
        if data.client_uuid is None:
            return None
        return await occurrence_repo.get_by_client_uuid(session, data.client_uuid)

    return await commit_idempotent(session, lambda: apply_occurrence(session, data, actor), _find)


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
    return await occurrence_repo.list_occurrences(
        session,
        page,
        kind=kind,
        location_id=location_id,
        sleeper_id=sleeper_id,
        start=start,
        end=end,
    )
