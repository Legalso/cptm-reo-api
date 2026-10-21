"""Catálogo de espécies de madeira."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import PageDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ALL_ROLES, SPECIES_ROLES
from app.models.user import User
from app.schemas.common import Page
from app.schemas.species import SpeciesCreate, SpeciesRead, SpeciesUpdate
from app.services import species as species_service

router = APIRouter(prefix="/especies", tags=["Espécies"])

Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]
Specialist = Annotated[User, Depends(require_roles(*SPECIES_ROLES))]


@router.get("", response_model=Page[SpeciesRead], summary="Listar espécies", responses=AUTH)
async def list_species(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    active: Annotated[bool | None, Query(description="Só ativas/inativas")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Código ou nome")] = None,
) -> Page[SpeciesRead]:
    items, total = await species_service.list_species(session, page, active=active, search=q)
    return Page(
        items=[SpeciesRead.model_validate(s) for s in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{species_id}",
    response_model=SpeciesRead,
    summary="Detalhe da espécie",
    responses={**AUTH, **errors(404)},
)
async def get_species(species_id: uuid.UUID, session: SessionDep, _: Reader) -> SpeciesRead:
    return SpeciesRead.model_validate(await species_service.get(session, species_id))


@router.post(
    "",
    response_model=SpeciesRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar espécie (especialista)",
    responses={**AUTH_VALIDATION, **errors(409)},
)
async def create_species(
    data: SpeciesCreate, session: SessionDep, actor: Specialist
) -> SpeciesRead:
    return SpeciesRead.model_validate(await species_service.create(session, data, actor))


@router.patch(
    "/{species_id}",
    response_model=SpeciesRead,
    summary="Editar espécie (especialista)",
    responses={**AUTH_VALIDATION, **errors(404)},
)
async def update_species(
    species_id: uuid.UUID, data: SpeciesUpdate, session: SessionDep, actor: Specialist
) -> SpeciesRead:
    return SpeciesRead.model_validate(
        await species_service.update(session, species_id, data, actor)
    )
