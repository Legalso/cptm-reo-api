"""Inspeção digital de dormentes."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, NotFoundError
from app.core.permissions import SPECIES_ROLES, has_role
from app.models.enums import InspectionResult, SleeperStatus
from app.models.inspection import Inspection
from app.models.sleeper import Sleeper
from app.models.user import User
from app.repositories import inspections as inspection_repo
from app.schemas.common import PageParams
from app.schemas.operations import InspectionCreate
from app.services import audit, clock
from app.services import sleepers as sleeper_service
from app.services import species as species_service
from app.services.idempotency import commit_idempotent


def _status_after(sleeper: Sleeper, result: InspectionResult) -> SleeperStatus:
    """Reprovação → quarentena (CONTEXTO). Aprovação libera a quarentena de quem está
    no pátio; fora do pátio a liberação é manual (não sabemos o status anterior)."""
    if result == InspectionResult.REJECTED:
        return SleeperStatus.QUARANTINE
    if sleeper.status == SleeperStatus.QUARANTINE and sleeper.current_location_id:
        return SleeperStatus.IN_STOCK
    return sleeper.status


async def apply_inspection(
    session: AsyncSession, data: InspectionCreate, actor: User
) -> tuple[Inspection, bool]:
    """Registra a inspeção e aplica os efeitos no dormente (sem commit).

    `species_corrected_id` sempre fica registrado; só muda a espécie do dormente
    quando quem inspeciona é especialista (ou admin).
    """
    if data.client_uuid:
        existing = await inspection_repo.get_by_client_uuid(session, data.client_uuid)
        if existing is not None:
            return existing, False
    inspected_at = clock.resolve_occurred_at(data.inspected_at)
    sleeper = await sleeper_service.resolve_for_update(session, data.sleeper_id, data.rfid_tag)
    if sleeper.status == SleeperStatus.DISCARDED:
        raise BusinessRuleError("Dormente descartado não é inspecionado.", code="sleeper_discarded")
    if data.species_corrected_id:
        await species_service.get(session, data.species_corrected_id)

    changes: dict[str, object] = {"status": _status_after(sleeper, data.result)}
    if data.species_corrected_id and has_role(actor.role, SPECIES_ROLES):
        changes["species_id"] = data.species_corrected_id
    await audit.update_with_audit(
        session, sleeper, changes, actor_id=actor.id, entity="sleeper", action="inspection"
    )

    inspection = Inspection(
        **data.model_dump(exclude={"sleeper_id", "rfid_tag", "inspected_at"}),
        sleeper_id=sleeper.id,
        inspector_id=actor.id,
        inspected_at=inspected_at,
    )
    await audit.create_with_audit(session, inspection, actor_id=actor.id, entity="inspection")
    return inspection, True


async def register_inspection(
    session: AsyncSession, data: InspectionCreate, actor: User
) -> tuple[Inspection, bool]:
    """`POST /inspecoes`."""

    async def _find() -> Inspection | None:
        if data.client_uuid is None:
            return None
        return await inspection_repo.get_by_client_uuid(session, data.client_uuid)

    return await commit_idempotent(session, lambda: apply_inspection(session, data, actor), _find)


async def get(session: AsyncSession, inspection_id: uuid.UUID) -> Inspection:
    inspection = await inspection_repo.get_by_id(session, inspection_id)
    if inspection is None:
        raise NotFoundError("Inspeção não encontrada.", code="inspection_not_found")
    return inspection


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
    return await inspection_repo.list_inspections(
        session,
        page,
        sleeper_id=sleeper_id,
        result=result,
        inspector_id=inspector_id,
        start=start,
        end=end,
    )
