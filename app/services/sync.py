"""Sincronização offline: processa o lote item a item reaproveitando os services.

Cada item roda num SAVEPOINT: se falhar, só ele é desfeito e o lote segue.
Reenviar o mesmo lote devolve `duplicate` para tudo (upsert por `client_uuid`).
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import INSPECTION_ROLES, has_role
from app.db.base import Base
from app.db.mixins import utcnow
from app.models.enums import SyncBatchStatus, SyncItemStatus
from app.models.sync_batch import SyncBatch
from app.models.user import User
from app.repositories import inspections as inspection_repo
from app.repositories import inventory as inventory_repo
from app.repositories import movements as movement_repo
from app.repositories import occurrences as occurrence_repo
from app.repositories import sync_batches as sync_repo
from app.schemas.operations import (
    InspectionCreate,
    InventoryCountCreate,
    MovementCreate,
    OccurrenceCreate,
)
from app.schemas.sync import ItemType, SyncBatchRequest, SyncItemResult
from app.services import audit, inspections, inventory, movements, occurrences

logger = logging.getLogger(__name__)

Applier = Callable[[AsyncSession, Any, User], Awaitable[tuple[Base, bool]]]
Finder = Callable[[AsyncSession, uuid.UUID], Awaitable[Base | None]]


@dataclass(frozen=True)
class _Handler:
    schema: type[BaseModel]
    time_field: str
    apply: Applier
    find: Finder


HANDLERS: dict[ItemType, _Handler] = {
    "movement": _Handler(
        MovementCreate, "occurred_at", movements.apply_movement, movement_repo.get_by_client_uuid
    ),
    "inspection": _Handler(
        InspectionCreate,
        "inspected_at",
        inspections.apply_inspection,
        inspection_repo.get_by_client_uuid,
    ),
    "occurrence": _Handler(
        OccurrenceCreate,
        "occurred_at",
        occurrences.apply_occurrence,
        occurrence_repo.get_by_client_uuid,
    ),
    "inventory_count": _Handler(
        InventoryCountCreate,
        "counted_at",
        inventory.apply_count,
        inventory_repo.get_by_client_uuid,
    ),
}


@dataclass
class _Item:
    type: ItemType
    index: int
    data: Any
    when: datetime


def _rejected(
    item_type: ItemType, index: int, client_uuid: uuid.UUID | None, code: str, reason: str
) -> SyncItemResult:
    return SyncItemResult(
        type=item_type,
        index=index,
        client_uuid=client_uuid,
        status=SyncItemStatus.REJECTED,
        code=code,
        reason=reason,
    )


def _raw_client_uuid(raw: dict[str, Any]) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw["client_uuid"]))
    except (KeyError, ValueError, TypeError):
        return None


def _parse(request: SyncBatchRequest, actor: User) -> tuple[list[_Item], list[SyncItemResult]]:
    """Valida cada item isoladamente; os inválidos já viram `rejected`."""
    groups: list[tuple[ItemType, list[dict[str, Any]]]] = [
        ("movement", request.movements),
        ("inspection", request.inspections),
        ("occurrence", request.occurrences),
        ("inventory_count", request.inventory_counts),
    ]
    items: list[_Item] = []
    rejected: list[SyncItemResult] = []
    received = utcnow()
    for item_type, raws in groups:
        handler = HANDLERS[item_type]
        for index, raw in enumerate(raws):
            client_uuid = _raw_client_uuid(raw)
            if client_uuid is None:
                rejected.append(
                    _rejected(
                        item_type,
                        index,
                        None,
                        "client_uuid_required",
                        "Item de sync precisa de client_uuid válido.",
                    )
                )
                continue
            if item_type == "inspection" and not has_role(actor.role, INSPECTION_ROLES):
                rejected.append(
                    _rejected(
                        item_type,
                        index,
                        client_uuid,
                        "forbidden",
                        "Seu papel não registra inspeções.",
                    )
                )
                continue
            try:
                data = handler.schema.model_validate(raw)
            except ValidationError as exc:
                first = exc.errors()[0]
                where = ".".join(str(p) for p in first["loc"]) or "item"
                rejected.append(
                    _rejected(
                        item_type,
                        index,
                        client_uuid,
                        "validation_error",
                        f"Dados inválidos em '{where}': {first['msg']}",
                    )
                )
                continue
            when = getattr(data, handler.time_field) or received
            items.append(_Item(item_type, index, data, when))
    return items, rejected


async def _process(session: AsyncSession, item: _Item, actor: User) -> SyncItemResult:
    """Aplica um item dentro de um savepoint e traduz o desfecho."""
    handler = HANDLERS[item.type]
    client_uuid: uuid.UUID = item.data.client_uuid
    try:
        async with session.begin_nested():
            record, created = await handler.apply(session, item.data, actor)
    except AppError as exc:
        return _rejected(item.type, item.index, client_uuid, exc.code, exc.detail)
    except IntegrityError:
        # Mesmo client_uuid gravado em paralelo: é duplicado, não erro.
        existing = await handler.find(session, client_uuid)
        if existing is None:
            return _rejected(
                item.type, item.index, client_uuid, "conflict", "Registro conflitante."
            )
        record, created = existing, False
    status = SyncItemStatus.ACCEPTED if created else SyncItemStatus.DUPLICATE
    return SyncItemResult(
        type=item.type,
        index=item.index,
        client_uuid=client_uuid,
        status=status,
        id=getattr(record, "id", None),
    )


def _batch_status(accepted: int, duplicate: int, rejected: int) -> SyncBatchStatus:
    if rejected == 0:
        return SyncBatchStatus.COMPLETED
    if accepted + duplicate == 0:
        return SyncBatchStatus.FAILED
    return SyncBatchStatus.PARTIAL


async def replicate(session: AsyncSession, request: SyncBatchRequest, actor: User) -> SyncBatch:
    """`POST /sincronizacao/replicar`: processa tudo, grava o SyncBatch e faz um commit."""
    received_at = utcnow()
    items, results = _parse(request, actor)
    # Ordem cronológica dos eventos; empate mantém a ordem de envio.
    for item in sorted(items, key=lambda i: i.when):
        results.append(await _process(session, item, actor))
    results.sort(key=lambda r: (list(HANDLERS).index(r.type), r.index))

    counts = {status: 0 for status in SyncItemStatus}
    for result in results:
        counts[result.status] += 1
    batch = SyncBatch(
        user_id=actor.id,
        device_id=request.device_id,
        received_at=received_at,
        total=len(results),
        accepted=counts[SyncItemStatus.ACCEPTED],
        duplicate=counts[SyncItemStatus.DUPLICATE],
        rejected=counts[SyncItemStatus.REJECTED],
        status=_batch_status(
            counts[SyncItemStatus.ACCEPTED],
            counts[SyncItemStatus.DUPLICATE],
            counts[SyncItemStatus.REJECTED],
        ),
        results=[r.model_dump(mode="json") for r in results],
    )
    session.add(batch)
    await session.flush()
    await audit.record(
        session,
        actor_id=actor.id,
        action="sync",
        entity="sync_batch",
        entity_id=batch.id,
        after={k: v for k, v in audit.snapshot(batch).items() if k != "results"},
    )
    await session.commit()
    logger.info(
        "Lote %s: %s aceitos, %s duplicados, %s rejeitados",
        batch.id,
        batch.accepted,
        batch.duplicate,
        batch.rejected,
    )
    return batch


async def latest(session: AsyncSession, actor: User, device_id: str | None) -> SyncBatch | None:
    """Último lote do usuário (filtrado pelo aparelho, se informado)."""
    return await sync_repo.get_latest(session, actor.id, device_id)
