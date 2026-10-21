"""Regras críticas da sincronização offline."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SleeperStatus, SyncBatchStatus
from app.models.movement import Movement
from app.schemas.sync import SyncBatchRequest
from app.services import sync
from tests.conftest import Catalog, SleeperFactory, UserFactory


def transfer(tag: str, to: uuid.UUID, at: str, client: uuid.UUID | None = None) -> dict[str, Any]:
    return {
        "client_uuid": str(client or uuid.uuid4()),
        "rfid_tag": tag,
        "kind": "transfer",
        "to_location_id": str(to),
        "occurred_at": at,
    }


def rejected_inspection(tag: str, at: str) -> dict[str, Any]:
    return {
        "client_uuid": str(uuid.uuid4()),
        "rfid_tag": tag,
        "inspected_at": at,
        "conservation": "poor",
        "has_cracks": True,
        "biological_attack": True,
        "moisture": "wet",
        "result": "rejected",
    }


async def test_resending_same_batch_duplicates_nothing(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user(Role.TECHNICIAN)
    sleeper = await make_sleeper()
    request = SyncBatchRequest(
        device_id="coletor-1",
        movements=[transfer(sleeper.rfid_tag, catalog.other_street.id, "2026-10-21T10:00:00Z")],
        inspections=[rejected_inspection(sleeper.rfid_tag, "2026-10-21T11:00:00Z")],
    )

    first = await sync.replicate(session, request, actor)
    second = await sync.replicate(session, request, actor)

    assert (first.accepted, first.duplicate, first.rejected) == (2, 0, 0)
    assert first.status == SyncBatchStatus.COMPLETED
    assert (second.accepted, second.duplicate, second.rejected) == (0, 2, 0)
    assert [r["id"] for r in first.results] == [r["id"] for r in second.results]
    total = await session.scalar(select(func.count()).select_from(Movement))
    assert total == 1


async def test_bad_item_does_not_break_batch(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    actor = await make_user()
    good = await make_sleeper()
    discarded = await make_sleeper(status=SleeperStatus.DISCARDED)
    request = SyncBatchRequest(
        movements=[
            transfer(good.rfid_tag, catalog.other_street.id, "2026-10-21T10:00:00Z"),
            transfer(discarded.rfid_tag, catalog.other_street.id, "2026-10-21T10:01:00Z"),
            {"rfid_tag": good.rfid_tag, "kind": "transfer"},  # sem client_uuid
            {"client_uuid": str(uuid.uuid4()), "rfid_tag": "X", "kind": "voar"},
            transfer("TAG-INEXISTENTE", catalog.street.id, "2026-10-21T10:02:00Z"),
        ],
        occurrences=[
            {
                "client_uuid": str(uuid.uuid4()),
                "rfid_tag": good.rfid_tag,
                "kind": "damage",
                "description": "Lascado",
            }
        ],
    )

    batch = await sync.replicate(session, request, actor)

    by_index = {(r["type"], r["index"]): r for r in batch.results}
    assert by_index[("movement", 0)]["status"] == "accepted"
    assert by_index[("movement", 1)]["code"] == "sleeper_discarded"
    assert by_index[("movement", 2)]["code"] == "client_uuid_required"
    assert by_index[("movement", 3)]["code"] == "validation_error"
    assert by_index[("movement", 4)]["code"] == "sleeper_not_found"
    assert by_index[("occurrence", 0)]["status"] == "accepted"
    assert batch.status == SyncBatchStatus.PARTIAL
    assert good.current_location_id == catalog.other_street.id


async def test_items_apply_in_chronological_order_across_lists(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory, catalog: Catalog
) -> None:
    """Inspeção reprovada às 9h e retirada às 10h: a retirada precisa ser rejeitada
    (quarentena), mesmo vindo antes na lista."""
    actor = await make_user(Role.TECHNICIAN)
    sleeper = await make_sleeper()
    request = SyncBatchRequest(
        movements=[
            {
                "client_uuid": str(uuid.uuid4()),
                "rfid_tag": sleeper.rfid_tag,
                "kind": "withdrawal",
                "requisition_number": "RM-9",
                "occurred_at": "2026-10-21T10:00:00Z",
            }
        ],
        inspections=[rejected_inspection(sleeper.rfid_tag, "2026-10-21T09:00:00Z")],
    )

    batch = await sync.replicate(session, request, actor)

    results = {r["type"]: r for r in batch.results}
    assert results["inspection"]["status"] == "accepted"
    assert results["movement"]["code"] == "sleeper_quarantined"
    assert sleeper.status == SleeperStatus.QUARANTINE


async def test_operator_cannot_sync_inspections(
    session: AsyncSession, make_user: UserFactory, make_sleeper: SleeperFactory
) -> None:
    actor = await make_user(Role.OPERATOR)
    sleeper = await make_sleeper()
    request = SyncBatchRequest(
        inspections=[rejected_inspection(sleeper.rfid_tag, "2026-10-21T09:00:00Z")]
    )
    batch = await sync.replicate(session, request, actor)
    assert batch.status == SyncBatchStatus.FAILED
    assert batch.results[0]["code"] == "forbidden"
    assert sleeper.status == SleeperStatus.IN_STOCK
