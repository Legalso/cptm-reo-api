"""Locais físicos (pátios e ruas)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import PageDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ALL_ROLES, MANAGEMENT_ROLES
from app.models.enums import LocationKind
from app.models.user import User
from app.schemas.common import Page
from app.schemas.location import LocationCreate, LocationRead, LocationUpdate
from app.services import locations as location_service

router = APIRouter(prefix="/locais", tags=["Locais"])

Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]
Manager = Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))]


@router.get("", response_model=Page[LocationRead], summary="Listar locais", responses=AUTH)
async def list_locations(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    kind: Annotated[LocationKind | None, Query(description="warehouse ou street")] = None,
    parent_id: Annotated[uuid.UUID | None, Query(description="Ruas de um pátio")] = None,
    active: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100, description="Parte do nome")] = None,
) -> Page[LocationRead]:
    items, total = await location_service.list_locations(
        session, page, kind=kind, parent_id=parent_id, active=active, search=q
    )
    return Page(
        items=[LocationRead.model_validate(loc) for loc in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{location_id}",
    response_model=LocationRead,
    summary="Detalhe do local",
    responses={**AUTH, **errors(404)},
)
async def get_location(location_id: uuid.UUID, session: SessionDep, _: Reader) -> LocationRead:
    return LocationRead.model_validate(await location_service.get(session, location_id))


@router.post(
    "",
    response_model=LocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar local (supervisor)",
    responses={**AUTH_VALIDATION, **errors(404, 409)},
)
async def create_location(
    data: LocationCreate, session: SessionDep, actor: Manager
) -> LocationRead:
    return LocationRead.model_validate(await location_service.create(session, data, actor))


@router.patch(
    "/{location_id}",
    response_model=LocationRead,
    summary="Editar/desativar local (supervisor)",
    responses={**AUTH_VALIDATION, **errors(404, 409)},
)
async def update_location(
    location_id: uuid.UUID, data: LocationUpdate, session: SessionDep, actor: Manager
) -> LocationRead:
    return LocationRead.model_validate(
        await location_service.update(session, location_id, data, actor)
    )
