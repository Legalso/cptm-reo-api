"""Idempotência por client_uuid, inclusive na corrida entre duas requisições."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.enums import (
    ConservationState,
    InspectionResult,
    MoistureLevel,
    Role,
    SleeperStatus,
)
from app.models.inventory import InventoryCount
from app.repositories import inventory as inventory_repo
from app.schemas.operations import InspectionCreate, InventoryCountCreate
from app.services import inspections, inventory
from app.services.idempotency import commit_idempotent
from tests.conftest import Catalog, SleeperFactory, UserFactory


async def test_inventory_resend_returns_same_record(
    session: AsyncSession, make_user: UserFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    data = InventoryCountCreate(
        location_id=catalog.street.id,
        species_id=catalog.species.id,
        quantity=10,
        client_uuid=uuid.uuid4(),
    )
    first, created = await inventory.register_count(session, data, actor)
    again, created_again = await inventory.register_count(session, data, actor)
    assert created and not created_again
    assert first.id == again.id


async def test_race_on_client_uuid_becomes_duplicate(
    session: AsyncSession, make_user: UserFactory, catalog: Catalog
) -> None:
    """Simula a requisição concorrente: a checagem prévia não viu o registro, mas o
    INSERT bate na unique. O resultado deve ser 'duplicado', não erro 500."""
    actor = await make_user()
    client_uuid = uuid.uuid4()
    data = InventoryCountCreate(
        location_id=catalog.street.id,
        species_id=catalog.species.id,
        quantity=5,
        client_uuid=client_uuid,
    )
    winner, _ = await inventory.register_count(session, data, actor)

    async def racing_insert() -> tuple[InventoryCount, bool]:
        clone = InventoryCount(
            location_id=catalog.street.id,
            species_id=catalog.species.id,
            counted_at=winner.counted_at,
            quantity=5,
            user_id=actor.id,
            client_uuid=client_uuid,
        )
        session.add(clone)
        await session.flush()
        return clone, True

    result, created = await commit_idempotent(
        session, racing_insert, lambda: inventory_repo.get_by_client_uuid(session, client_uuid)
    )
    assert not created
    assert result.id == winner.id


async def test_discarded_sleeper_is_not_inspected(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    sleeper = await make_sleeper(status=SleeperStatus.DISCARDED)
    data = InspectionCreate(
        sleeper_id=sleeper.id,
        conservation=ConservationState.POOR,
        has_cracks=True,
        biological_attack=True,
        moisture=MoistureLevel.WET,
        result=InspectionResult.REJECTED,
    )
    with pytest.raises(AppError) as exc:
        await inspections.apply_inspection(session, data, await make_user(Role.TECHNICIAN))
    assert exc.value.code == "sleeper_discarded"
