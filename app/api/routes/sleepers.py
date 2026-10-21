"""Dormentes: consulta (inclusive por tag RFID), cadastro, edição e histórico."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.api.deps import PageDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ALL_ROLES, FIELD_ROLES
from app.models.enums import SleeperStatus
from app.models.user import User
from app.schemas.common import Page, normalize_tag
from app.schemas.sleeper import (
    SleeperCreate,
    SleeperHistory,
    SleeperRead,
    SleeperUpdate,
)
from app.services import sleepers as sleeper_service

router = APIRouter(prefix="/dormentes", tags=["Dormentes"])

Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]
FieldUser = Annotated[User, Depends(require_roles(*FIELD_ROLES))]


@router.get("", response_model=Page[SleeperRead], summary="Listar dormentes", responses=AUTH)
async def list_sleepers(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    status_: Annotated[SleeperStatus | None, Query(alias="status")] = None,
    species_id: Annotated[uuid.UUID | None, Query()] = None,
    location_id: Annotated[
        uuid.UUID | None, Query(description="Local atual; pátio inclui suas ruas")
    ] = None,
    q: Annotated[str | None, Query(max_length=64, description="Parte da ata ou da tag")] = None,
) -> Page[SleeperRead]:
    items, total = await sleeper_service.list_sleepers(
        session, page, status=status_, species_id=species_id, location_id=location_id, search=q
    )
    return Page(
        items=[SleeperRead.model_validate(s) for s in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/tag/{rfid_tag}",
    response_model=SleeperRead,
    summary="Buscar dormente pela tag RFID",
    responses={**AUTH, **errors(404)},
)
async def get_by_tag(
    rfid_tag: Annotated[str, Path(min_length=1, max_length=64)],
    session: SessionDep,
    _: Reader,
) -> SleeperRead:
    """404 com `code="sleeper_not_found"` quando a tag não existe: o app abre o cadastro."""
    return SleeperRead.model_validate(
        await sleeper_service.get_by_tag(session, normalize_tag(rfid_tag))
    )


@router.get(
    "/{sleeper_id}",
    response_model=SleeperRead,
    summary="Detalhe do dormente",
    responses={**AUTH, **errors(404)},
)
async def get_sleeper(sleeper_id: uuid.UUID, session: SessionDep, _: Reader) -> SleeperRead:
    return SleeperRead.model_validate(await sleeper_service.get(session, sleeper_id))


@router.get(
    "/{sleeper_id}/historico",
    response_model=SleeperHistory,
    summary="Histórico do dormente (movimentações, inspeções, ocorrências)",
    responses={**AUTH, **errors(404)},
)
async def get_history(sleeper_id: uuid.UUID, session: SessionDep, _: Reader) -> SleeperHistory:
    return await sleeper_service.history(session, sleeper_id)


@router.post(
    "",
    response_model=SleeperRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar dormente (gera entrada no estoque)",
    responses={
        200: {"model": SleeperRead, "description": "Reenvio com o mesmo client_uuid"},
        **AUTH_VALIDATION,
        **errors(404, 409),
    },
)
async def create_sleeper(
    data: SleeperCreate, session: SessionDep, actor: FieldUser, response: Response
) -> SleeperRead:
    sleeper, created = await sleeper_service.create(session, data, actor)
    if not created:
        response.status_code = status.HTTP_200_OK
    return SleeperRead.model_validate(sleeper)


@router.patch(
    "/{sleeper_id}",
    response_model=SleeperRead,
    summary="Editar dormente (espécie: especialista; status: técnico+)",
    responses={**AUTH_VALIDATION, **errors(404, 409)},
)
async def update_sleeper(
    sleeper_id: uuid.UUID, data: SleeperUpdate, session: SessionDep, actor: FieldUser
) -> SleeperRead:
    return SleeperRead.model_validate(
        await sleeper_service.update(session, sleeper_id, data, actor)
    )
