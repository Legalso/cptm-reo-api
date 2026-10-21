"""Contagens de inventário."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryCount
from app.models.user import User
from app.repositories import inventory as inventory_repo
from app.schemas.common import PageParams
from app.schemas.operations import InventoryCountCreate
from app.services import audit, clock
from app.services import locations as location_service
from app.services import species as species_service
from app.services.idempotency import commit_idempotent


async def apply_count(
    session: AsyncSession, data: InventoryCountCreate, actor: User
) -> tuple[InventoryCount, bool]:
    """Grava a contagem como veio da ficha (sem commit; reaproveitado pelo sync).

    TODO(decidir): conciliação contagem física x sistema. Por ora as tags lidas só
    ficam guardadas para quando a regra existir.
    """
    if data.client_uuid:
        existing = await inventory_repo.get_by_client_uuid(session, data.client_uuid)
        if existing is not None:
            return existing, False
    counted_at = clock.resolve_occurred_at(data.counted_at)
    await location_service.get(session, data.location_id)
    await species_service.get(session, data.species_id)
    count = InventoryCount(
        location_id=data.location_id,
        species_id=data.species_id,
        counted_at=counted_at,
        quantity=data.quantity,
        read_tags=data.read_tags,
        notes=data.notes,
        user_id=actor.id,
        client_uuid=data.client_uuid,
    )
    await audit.create_with_audit(session, count, actor_id=actor.id, entity="inventory_count")
    return count, True


async def register_count(
    session: AsyncSession, data: InventoryCountCreate, actor: User
) -> tuple[InventoryCount, bool]:
    """`POST /estoque/inventario`."""

    async def _find() -> InventoryCount | None:
        if data.client_uuid is None:
            return None
        return await inventory_repo.get_by_client_uuid(session, data.client_uuid)

    return await commit_idempotent(session, lambda: apply_count(session, data, actor), _find)


async def list_counts(
    session: AsyncSession,
    page: PageParams,
    *,
    location_id: uuid.UUID | None,
    species_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[InventoryCount], int]:
    return await inventory_repo.list_counts(
        session, page, location_id=location_id, species_id=species_id, start=start, end=end
    )
