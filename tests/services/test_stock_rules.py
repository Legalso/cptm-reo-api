"""Regras de negócio de movimentação, inspeção, ocorrência e inventário (no service)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.models.enums import (
    ConservationState,
    InspectionResult,
    MoistureLevel,
    MovementKind,
    OccurrenceKind,
    Role,
    SleeperStatus,
)
from app.schemas.operations import (
    InspectionCreate,
    InventoryCountCreate,
    LocationAssign,
    MovementCreate,
    OccurrenceCreate,
)
from app.services import inspections, inventory, movements, occurrences
from tests.conftest import Catalog, SleeperFactory, UserFactory


def inspection(
    sleeper_id: uuid.UUID, result: InspectionResult, **extra: object
) -> InspectionCreate:
    return InspectionCreate.model_validate(
        {
            "sleeper_id": sleeper_id,
            "conservation": ConservationState.POOR,
            "has_cracks": True,
            "biological_attack": False,
            "moisture": MoistureLevel.DRY,
            "result": result,
            **extra,
        }
    )


async def test_discarded_sleeper_does_not_move(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    sleeper = await make_sleeper(status=SleeperStatus.DISCARDED)
    data = MovementCreate(
        sleeper_id=sleeper.id, kind=MovementKind.TRANSFER, to_location_id=catalog.other_street.id
    )
    with pytest.raises(AppError) as exc:
        await movements.apply_movement(session, data, actor)
    assert exc.value.code == "sleeper_discarded"


async def test_withdrawal_sets_withdrawn_and_clears_location(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    sleeper = await make_sleeper()
    data = MovementCreate(
        rfid_tag=sleeper.rfid_tag.lower(), kind=MovementKind.WITHDRAWAL, requisition_number="RM-1"
    )

    movement, created = await movements.apply_movement(session, data, actor)

    assert created
    assert movement.from_location_id == catalog.street.id and movement.to_location_id is None
    assert sleeper.status == SleeperStatus.WITHDRAWN
    assert sleeper.current_location_id is None


async def test_quarantined_sleeper_cannot_be_withdrawn(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    sleeper = await make_sleeper(status=SleeperStatus.QUARANTINE)
    data = MovementCreate(
        sleeper_id=sleeper.id, kind=MovementKind.WITHDRAWAL, requisition_number="RM-2"
    )
    with pytest.raises(AppError) as exc:
        await movements.apply_movement(session, data, await make_user())
    assert exc.value.code == "sleeper_quarantined"


async def test_entry_requires_sleeper_outside_yard(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    in_yard = await make_sleeper()
    with pytest.raises(AppError) as exc:
        await movements.apply_movement(
            session,
            MovementCreate(
                sleeper_id=in_yard.id, kind=MovementKind.ENTRY, to_location_id=catalog.street.id
            ),
            actor,
        )
    assert exc.value.code == "already_in_yard"

    returning = await make_sleeper(status=SleeperStatus.IN_TRACK)
    await movements.apply_movement(
        session,
        MovementCreate(
            sleeper_id=returning.id, kind=MovementKind.ENTRY, to_location_id=catalog.street.id
        ),
        actor,
    )
    assert returning.status == SleeperStatus.IN_STOCK
    assert returning.current_location_id == catalog.street.id


async def test_transfer_rules(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    sleeper = await make_sleeper(status=SleeperStatus.QUARANTINE)
    same = MovementCreate(
        sleeper_id=sleeper.id, kind=MovementKind.TRANSFER, to_location_id=catalog.street.id
    )
    with pytest.raises(AppError) as exc:
        await movements.apply_movement(session, same, actor)
    assert exc.value.code == "same_location"

    ok = MovementCreate(
        sleeper_id=sleeper.id, kind=MovementKind.TRANSFER, to_location_id=catalog.other_street.id
    )
    await movements.apply_movement(session, ok, actor)
    assert sleeper.current_location_id == catalog.other_street.id
    assert sleeper.status == SleeperStatus.QUARANTINE  # transferência não muda status


async def test_movement_is_idempotent_by_client_uuid(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    sleeper = await make_sleeper()
    data = MovementCreate(
        sleeper_id=sleeper.id,
        kind=MovementKind.TRANSFER,
        to_location_id=catalog.other_street.id,
        client_uuid=uuid.uuid4(),
    )
    first, created_first = await movements.apply_movement(session, data, actor)
    second, created_second = await movements.apply_movement(session, data, actor)
    assert created_first and not created_second
    assert first.id == second.id


async def test_location_shortcut_picks_entry_or_transfer(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    outside = await make_sleeper(status=SleeperStatus.WITHDRAWN)
    inside = await make_sleeper()

    entry, _ = await movements.apply_location(
        session, LocationAssign(sleeper_id=outside.id, location_id=catalog.street.id), actor
    )
    transfer, _ = await movements.apply_location(
        session, LocationAssign(sleeper_id=inside.id, location_id=catalog.other_street.id), actor
    )
    assert entry.kind == MovementKind.ENTRY
    assert transfer.kind == MovementKind.TRANSFER


async def test_unknown_tag_is_not_found(session: AsyncSession, make_user: UserFactory) -> None:
    data = MovementCreate(rfid_tag="NOPE", kind=MovementKind.WITHDRAWAL, requisition_number="RM")
    with pytest.raises(NotFoundError):
        await movements.apply_movement(session, data, await make_user())


async def test_rejected_inspection_quarantines_and_approval_releases(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    tech = await make_user(Role.TECHNICIAN)
    sleeper = await make_sleeper()

    await inspections.apply_inspection(
        session, inspection(sleeper.id, InspectionResult.REJECTED), tech
    )
    assert sleeper.status == SleeperStatus.QUARANTINE

    await inspections.apply_inspection(
        session, inspection(sleeper.id, InspectionResult.APPROVED), tech
    )
    assert sleeper.status == SleeperStatus.IN_STOCK


async def test_species_correction_applies_only_for_specialist(
    session: AsyncSession,
    make_user: UserFactory,
    make_sleeper: SleeperFactory,
    catalog: Catalog,
) -> None:
    from app.models.species import WoodSpecies

    other = WoodSpecies(code="09", scientific_name="Dipteryx odorata")
    session.add(other)
    await session.flush()
    sleeper = await make_sleeper()

    tech = await make_user(Role.TECHNICIAN)
    recorded, _ = await inspections.apply_inspection(
        session,
        inspection(sleeper.id, InspectionResult.APPROVED, species_corrected_id=other.id),
        tech,
    )
    assert recorded.species_corrected_id == other.id
    assert sleeper.species_id == catalog.species.id

    specialist = await make_user(Role.SPECIALIST)
    await inspections.apply_inspection(
        session,
        inspection(sleeper.id, InspectionResult.APPROVED, species_corrected_id=other.id),
        specialist,
    )
    assert sleeper.species_id == other.id


async def test_occurrence_uses_sleeper_location(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    sleeper = await make_sleeper()
    occ, _ = await occurrences.apply_occurrence(
        session,
        OccurrenceCreate(
            rfid_tag=sleeper.rfid_tag, kind=OccurrenceKind.DAMAGE, description="Racha"
        ),
        actor,
    )
    assert occ.location_id == catalog.street.id
    assert sleeper.status == SleeperStatus.IN_STOCK  # ocorrência não muda status

    outside = await make_sleeper(status=SleeperStatus.IN_TRACK)
    with pytest.raises(AppError) as exc:
        await occurrences.apply_occurrence(
            session,
            OccurrenceCreate(sleeper_id=outside.id, kind=OccurrenceKind.LOSS, description="Sumiu"),
            actor,
        )
    assert exc.value.code == "location_required"


async def test_inventory_normalizes_tags(
    session: AsyncSession, make_user: UserFactory, catalog: Catalog
) -> None:
    count, created = await inventory.apply_count(
        session,
        InventoryCountCreate(
            location_id=catalog.street.id,
            species_id=catalog.species.id,
            quantity=2,
            read_tags=["abc", " ABC ", "def", ""],
        ),
        await make_user(),
    )
    assert created
    assert count.read_tags == ["ABC", "DEF"]
