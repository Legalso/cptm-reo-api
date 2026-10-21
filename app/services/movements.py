"""Movimentações de estoque e suas regras de status.

Regras (CONTEXTO.md + decisões do plano):
- descartado não movimenta;
- entrada: dormente fora do pátio (sem local) chega a um local → `in_stock`
  (ou continua `quarantine` se estava em quarentena);
- retirada: só de `in_stock` (quarentena não vai para a via), exige RM → `withdrawn`;
- transferência: dormente no pátio muda de local, status mantido.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError
from app.models.enums import MovementKind, SleeperStatus
from app.models.movement import Movement
from app.models.sleeper import Sleeper
from app.models.user import User
from app.repositories import movements as movement_repo
from app.schemas.common import PageParams
from app.schemas.operations import LocationAssign, MovementCreate
from app.services import audit, clock
from app.services import locations as location_service
from app.services import sleepers as sleeper_service
from app.services.idempotency import commit_idempotent


def _rule(detail: str, code: str) -> BusinessRuleError:
    return BusinessRuleError(detail, code=code)


async def _apply_to_sleeper(
    session: AsyncSession, sleeper: Sleeper, data: MovementCreate
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Valida a regra do tipo e muda o dormente. Devolve (origem, destino)."""
    if sleeper.status == SleeperStatus.DISCARDED:
        raise _rule("Dormente descartado não movimenta.", "sleeper_discarded")
    origin = sleeper.current_location_id

    if data.kind == MovementKind.ENTRY:
        if origin is not None:
            raise _rule("Dormente já está no pátio; use transferência.", "already_in_yard")
        assert data.to_location_id is not None
        await location_service.get_active(session, data.to_location_id)
        if sleeper.status != SleeperStatus.QUARANTINE:
            sleeper.status = SleeperStatus.IN_STOCK
        sleeper.current_location_id = data.to_location_id
        return None, data.to_location_id

    if data.kind == MovementKind.WITHDRAWAL:
        if sleeper.status == SleeperStatus.QUARANTINE:
            raise _rule("Dormente em quarentena não pode ir para a via.", "sleeper_quarantined")
        if sleeper.status != SleeperStatus.IN_STOCK:
            raise _rule("Só dormente em estoque pode ser retirado.", "not_in_stock")
        sleeper.status = SleeperStatus.WITHDRAWN
        sleeper.current_location_id = None
        return origin, None

    # Transferência.
    if origin is None:
        raise _rule("Dormente fora do pátio; registre uma entrada.", "not_in_yard")
    assert data.to_location_id is not None
    if data.to_location_id == origin:
        raise _rule("Dormente já está neste local.", "same_location")
    await location_service.get_active(session, data.to_location_id)
    sleeper.current_location_id = data.to_location_id
    return origin, data.to_location_id


async def apply_movement(
    session: AsyncSession, data: MovementCreate, actor: User
) -> tuple[Movement, bool]:
    """Aplica sem commit (o sync usa dentro de savepoint). Devolve (movimento, criado?)."""
    if data.client_uuid:
        existing = await movement_repo.get_by_client_uuid(session, data.client_uuid)
        if existing is not None:
            return existing, False
    occurred_at = clock.resolve_occurred_at(data.occurred_at)
    sleeper = await sleeper_service.resolve_for_update(session, data.sleeper_id, data.rfid_tag)

    before = audit.snapshot(sleeper)
    origin, destination = await _apply_to_sleeper(session, sleeper, data)
    await session.flush()
    await audit.record(
        session,
        actor_id=actor.id,
        action=f"movement_{data.kind}",
        entity="sleeper",
        entity_id=sleeper.id,
        before=before,
        after=audit.snapshot(sleeper),
    )
    movement = Movement(
        sleeper_id=sleeper.id,
        kind=data.kind,
        from_location_id=origin,
        to_location_id=destination,
        requisition_number=data.requisition_number,
        notes=data.notes,
        user_id=actor.id,
        occurred_at=occurred_at,
        client_uuid=data.client_uuid,
    )
    await audit.create_with_audit(session, movement, actor_id=actor.id, entity="movement")
    return movement, True


async def _find(session: AsyncSession, client_uuid: uuid.UUID | None) -> Movement | None:
    if client_uuid is None:
        return None
    return await movement_repo.get_by_client_uuid(session, client_uuid)


async def register_movement(
    session: AsyncSession, data: MovementCreate, actor: User
) -> tuple[Movement, bool]:
    """`POST /estoque/movimentacao`."""
    return await commit_idempotent(
        session,
        lambda: apply_movement(session, data, actor),
        lambda: _find(session, data.client_uuid),
    )


async def apply_location(
    session: AsyncSession, data: LocationAssign, actor: User
) -> tuple[Movement, bool]:
    """Atalho de posicionamento: dormente com local → transferência; sem local → entrada."""
    existing = await _find(session, data.client_uuid)
    if existing is not None:
        return existing, False
    sleeper = await sleeper_service.resolve_for_update(session, data.sleeper_id, data.rfid_tag)
    kind = MovementKind.TRANSFER if sleeper.current_location_id else MovementKind.ENTRY
    movement = MovementCreate(
        sleeper_id=sleeper.id,
        kind=kind,
        to_location_id=data.location_id,
        notes=data.notes,
        occurred_at=data.occurred_at,
        client_uuid=data.client_uuid,
    )
    return await apply_movement(session, movement, actor)


async def register_location(
    session: AsyncSession, data: LocationAssign, actor: User
) -> tuple[Movement, bool]:
    """`POST /estoque/localizacao`."""
    return await commit_idempotent(
        session,
        lambda: apply_location(session, data, actor),
        lambda: _find(session, data.client_uuid),
    )


async def list_movements(
    session: AsyncSession,
    page: PageParams,
    *,
    sleeper_id: uuid.UUID | None,
    kind: MovementKind | None,
    location_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[Movement], int]:
    return await movement_repo.list_movements(
        session,
        page,
        sleeper_id=sleeper_id,
        kind=kind,
        location_id=location_id,
        user_id=user_id,
        start=start,
        end=end,
    )
