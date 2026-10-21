"""Dormentes: cadastro, edição, consulta por tag e histórico."""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.core.permissions import INSPECTION_ROLES, SPECIES_ROLES, has_role
from app.models.enums import MovementKind, SleeperStatus
from app.models.movement import Movement
from app.models.sleeper import Sleeper
from app.models.user import User
from app.repositories import inspections as inspection_repo
from app.repositories import movements as movement_repo
from app.repositories import occurrences as occurrence_repo
from app.repositories import sleepers as sleeper_repo
from app.schemas.common import PageParams
from app.schemas.inspection import InspectionRead
from app.schemas.sleeper import (
    HistoryEntry,
    SleeperCreate,
    SleeperHistory,
    SleeperRead,
    SleeperUpdate,
)
from app.schemas.stock import MovementRead, OccurrenceRead
from app.services import audit, clock, species
from app.services import locations as location_service

# Status manual (PATCH): destino → origens permitidas. Entrada, retirada e
# transferência só via /estoque, porque mexem em local e exigem dados (RM, destino).
MANUAL_TRANSITIONS: dict[SleeperStatus, frozenset[SleeperStatus]] = {
    SleeperStatus.QUARANTINE: frozenset({SleeperStatus.IN_STOCK}),
    SleeperStatus.IN_STOCK: frozenset({SleeperStatus.QUARANTINE}),
    SleeperStatus.IN_TRACK: frozenset({SleeperStatus.WITHDRAWN}),
    SleeperStatus.DISCARDED: frozenset(set(SleeperStatus) - {SleeperStatus.DISCARDED}),
}


async def get(session: AsyncSession, sleeper_id: uuid.UUID) -> Sleeper:
    sleeper = await sleeper_repo.get_by_id(session, sleeper_id)
    if sleeper is None:
        raise NotFoundError("Dormente não encontrado.", code="sleeper_not_found")
    return sleeper


async def get_by_tag(session: AsyncSession, rfid_tag: str) -> Sleeper:
    """404 com code `sleeper_not_found`: o app usa isso para decidir "dormente novo"."""
    sleeper = await sleeper_repo.get_by_tag(session, rfid_tag)
    if sleeper is None:
        raise NotFoundError("Tag RFID não cadastrada.", code="sleeper_not_found")
    return sleeper


async def list_sleepers(
    session: AsyncSession,
    page: PageParams,
    *,
    status: SleeperStatus | None,
    species_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    search: str | None,
) -> tuple[list[Sleeper], int]:
    return await sleeper_repo.list_sleepers(
        session,
        page,
        status=status,
        species_id=species_id,
        location_id=location_id,
        search=search,
    )


async def _ensure_species_usable(session: AsyncSession, species_id: uuid.UUID) -> None:
    found = await species.get(session, species_id)
    if not found.active:
        raise BusinessRuleError("Espécie inativa no catálogo.", code="species_inactive")


async def create(session: AsyncSession, data: SleeperCreate, actor: User) -> tuple[Sleeper, bool]:
    """Cadastra o dormente em estoque e registra a entrada. Devolve (dormente, criado?).

    Reenvio com o mesmo `client_uuid` devolve o dormente já criado (idempotência).
    """
    if data.client_uuid:
        previous = await movement_repo.get_by_client_uuid(session, data.client_uuid)
        if previous is not None:
            return await get(session, previous.sleeper_id), False
    if await sleeper_repo.tag_exists(session, data.rfid_tag):
        raise ConflictError("Tag RFID já cadastrada.", code="rfid_tag_taken")
    location = await location_service.get_active(session, data.location_id)
    if data.species_id:
        await _ensure_species_usable(session, data.species_id)
    occurred_at = clock.resolve_occurred_at(data.occurred_at)

    plate = data.model_dump(exclude={"location_id", "occurred_at", "client_uuid"})
    sleeper = Sleeper(**plate, status=SleeperStatus.IN_STOCK, current_location_id=location.id)
    try:
        await audit.create_with_audit(session, sleeper, actor_id=actor.id, entity="sleeper")
        movement = Movement(
            sleeper_id=sleeper.id,
            kind=MovementKind.ENTRY,
            to_location_id=location.id,
            user_id=actor.id,
            occurred_at=occurred_at,
            client_uuid=data.client_uuid,
        )
        await audit.create_with_audit(session, movement, actor_id=actor.id, entity="movement")
        await session.commit()
    except IntegrityError as exc:
        # Corrida com outro cadastro da mesma tag/client_uuid.
        await session.rollback()
        raise ConflictError("Tag RFID já cadastrada.", code="rfid_tag_taken") from exc
    return await get(session, sleeper.id), True


def _check_status_change(actor: User, current: SleeperStatus, target: SleeperStatus) -> None:
    if not has_role(actor.role, INSPECTION_ROLES):
        raise ForbiddenError("Só técnico ou acima altera status manualmente.")
    if target == current:
        return
    if current == SleeperStatus.DISCARDED:
        raise BusinessRuleError("Dormente descartado não muda de status.", code="sleeper_discarded")
    allowed = MANUAL_TRANSITIONS.get(target, frozenset())
    if current not in allowed:
        raise BusinessRuleError(
            f"Transição {current} → {target} não é manual; use /estoque/movimentacao.",
            code="invalid_status_transition",
        )


async def update(
    session: AsyncSession, sleeper_id: uuid.UUID, data: SleeperUpdate, actor: User
) -> Sleeper:
    """Edição parcial com checagem fina de papel por campo."""
    sleeper = await get(session, sleeper_id)
    changes: dict[str, Any] = data.model_dump(exclude_unset=True)
    for key in ("rfid_tag", "status"):
        if key in changes and changes[key] is None:
            changes.pop(key)

    if "species_id" in changes and changes["species_id"] != sleeper.species_id:
        if not has_role(actor.role, SPECIES_ROLES):
            raise ForbiddenError("Só especialista altera a espécie do dormente.")
        if changes["species_id"] is not None:
            await _ensure_species_usable(session, changes["species_id"])
    if "status" in changes:
        _check_status_change(actor, sleeper.status, changes["status"])
    tag = changes.get("rfid_tag")
    if tag and tag != sleeper.rfid_tag and await sleeper_repo.tag_exists(session, tag):
        raise ConflictError("Tag RFID já cadastrada.", code="rfid_tag_taken")

    if await audit.update_with_audit(
        session, sleeper, changes, actor_id=actor.id, entity="sleeper"
    ):
        await session.commit()
    return await get(session, sleeper_id)


async def history(session: AsyncSession, sleeper_id: uuid.UUID) -> SleeperHistory:
    """Movimentações + inspeções + ocorrências numa linha do tempo única."""
    sleeper = await get(session, sleeper_id)
    items = [
        HistoryEntry(
            type="movement", occurred_at=m.occurred_at, movement=MovementRead.model_validate(m)
        )
        for m in await movement_repo.list_by_sleeper(session, sleeper_id)
    ]
    items += [
        HistoryEntry(
            type="inspection",
            occurred_at=i.inspected_at,
            inspection=InspectionRead.model_validate(i),
        )
        for i in await inspection_repo.list_by_sleeper(session, sleeper_id)
    ]
    items += [
        HistoryEntry(
            type="occurrence",
            occurred_at=o.occurred_at,
            occurrence=OccurrenceRead.model_validate(o),
        )
        for o in await occurrence_repo.list_by_sleeper(session, sleeper_id)
    ]
    items.sort(key=lambda entry: entry.occurred_at)
    return SleeperHistory(sleeper=SleeperRead.model_validate(sleeper), items=items)
