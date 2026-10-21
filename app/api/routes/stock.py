"""Operação de estoque: movimentação, posicionamento, inventário e ocorrências.

POSTs são idempotentes por `client_uuid`: 201 quando cria, 200 quando é reenvio.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import PageDep, PeriodDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ALL_ROLES, FIELD_ROLES
from app.models.enums import MovementKind, OccurrenceKind
from app.models.user import User
from app.schemas.common import Page
from app.schemas.operations import (
    InventoryCountCreate,
    LocationAssign,
    MovementCreate,
    OccurrenceCreate,
)
from app.schemas.stock import InventoryCountRead, MovementRead, OccurrenceRead
from app.services import inventory as inventory_service
from app.services import movements as movement_service
from app.services import occurrences as occurrence_service

router = APIRouter(prefix="/estoque", tags=["Estoque"])

Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]
FieldUser = Annotated[User, Depends(require_roles(*FIELD_ROLES))]

WRITE_ERRORS = {**AUTH_VALIDATION, **errors(404, 409)}


def _duplicate(model: type) -> dict[int | str, dict[str, object]]:
    return {200: {"model": model, "description": "Reenvio do mesmo client_uuid (nada criado)"}}


def _mark(response: Response, created: bool) -> None:
    if not created:
        response.status_code = status.HTTP_200_OK


@router.post(
    "/movimentacao",
    response_model=MovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar entrada, retirada ou transferência",
    responses={**_duplicate(MovementRead), **WRITE_ERRORS},
)
async def create_movement(
    data: MovementCreate, session: SessionDep, actor: FieldUser, response: Response
) -> MovementRead:
    movement, created = await movement_service.register_movement(session, data, actor)
    _mark(response, created)
    return MovementRead.model_validate(movement)


@router.post(
    "/localizacao",
    response_model=MovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Posicionar dormente num local (atalho de transferência/entrada)",
    responses={**_duplicate(MovementRead), **WRITE_ERRORS},
)
async def assign_location(
    data: LocationAssign, session: SessionDep, actor: FieldUser, response: Response
) -> MovementRead:
    movement, created = await movement_service.register_location(session, data, actor)
    _mark(response, created)
    return MovementRead.model_validate(movement)


@router.post(
    "/inventario",
    response_model=InventoryCountRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar contagem de inventário",
    responses={**_duplicate(InventoryCountRead), **WRITE_ERRORS},
)
async def create_inventory_count(
    data: InventoryCountCreate, session: SessionDep, actor: FieldUser, response: Response
) -> InventoryCountRead:
    count, created = await inventory_service.register_count(session, data, actor)
    _mark(response, created)
    return InventoryCountRead.model_validate(count)


@router.post(
    "/ocorrencias",
    response_model=OccurrenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar ocorrência (dano, perda, extravio...)",
    responses={**_duplicate(OccurrenceRead), **WRITE_ERRORS},
)
async def create_occurrence(
    data: OccurrenceCreate, session: SessionDep, actor: FieldUser, response: Response
) -> OccurrenceRead:
    occurrence, created = await occurrence_service.register_occurrence(session, data, actor)
    _mark(response, created)
    return OccurrenceRead.model_validate(occurrence)


@router.get(
    "/movimentacoes",
    response_model=Page[MovementRead],
    summary="Listar movimentações",
    responses={**AUTH, **errors(422)},
)
async def list_movements(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    period: PeriodDep,
    sleeper_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[MovementKind | None, Query()] = None,
    location_id: Annotated[uuid.UUID | None, Query(description="Origem ou destino")] = None,
    user_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[MovementRead]:
    items, total = await movement_service.list_movements(
        session,
        page,
        sleeper_id=sleeper_id,
        kind=kind,
        location_id=location_id,
        user_id=user_id,
        start=period.start,
        end=period.end,
    )
    return Page(
        items=[MovementRead.model_validate(m) for m in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/inventarios",
    response_model=Page[InventoryCountRead],
    summary="Listar contagens de inventário",
    responses={**AUTH, **errors(422)},
)
async def list_inventory_counts(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    period: PeriodDep,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
    species_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[InventoryCountRead]:
    items, total = await inventory_service.list_counts(
        session,
        page,
        location_id=location_id,
        species_id=species_id,
        start=period.start,
        end=period.end,
    )
    return Page(
        items=[InventoryCountRead.model_validate(c) for c in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/ocorrencias",
    response_model=Page[OccurrenceRead],
    summary="Listar ocorrências",
    responses={**AUTH, **errors(422)},
)
async def list_occurrences(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    period: PeriodDep,
    kind: Annotated[OccurrenceKind | None, Query()] = None,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
    sleeper_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[OccurrenceRead]:
    items, total = await occurrence_service.list_occurrences(
        session,
        page,
        kind=kind,
        location_id=location_id,
        sleeper_id=sleeper_id,
        start=period.start,
        end=period.end,
    )
    return Page(
        items=[OccurrenceRead.model_validate(o) for o in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
