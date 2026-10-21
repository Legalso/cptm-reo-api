"""Inspeções digitais (técnico e especialista registram; todos consultam)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import PageDep, PeriodDep, SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION, errors
from app.core.permissions import ALL_ROLES, INSPECTION_ROLES
from app.models.enums import InspectionResult
from app.models.user import User
from app.schemas.common import Page
from app.schemas.inspection import InspectionRead
from app.schemas.operations import InspectionCreate
from app.services import inspections as inspection_service

router = APIRouter(prefix="/inspecoes", tags=["Inspeções"])

Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]
Inspector = Annotated[User, Depends(require_roles(*INSPECTION_ROLES))]


@router.post(
    "",
    response_model=InspectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar inspeção (reprovada → quarentena)",
    responses={
        200: {"model": InspectionRead, "description": "Reenvio do mesmo client_uuid"},
        **AUTH_VALIDATION,
        **errors(404, 409),
    },
)
async def create_inspection(
    data: InspectionCreate, session: SessionDep, actor: Inspector, response: Response
) -> InspectionRead:
    inspection, created = await inspection_service.register_inspection(session, data, actor)
    if not created:
        response.status_code = status.HTTP_200_OK
    return InspectionRead.model_validate(inspection)


@router.get(
    "",
    response_model=Page[InspectionRead],
    summary="Listar inspeções",
    responses={**AUTH, **errors(422)},
)
async def list_inspections(
    session: SessionDep,
    _: Reader,
    page: PageDep,
    period: PeriodDep,
    sleeper_id: Annotated[uuid.UUID | None, Query()] = None,
    result: Annotated[InspectionResult | None, Query()] = None,
    inspector_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[InspectionRead]:
    items, total = await inspection_service.list_inspections(
        session,
        page,
        sleeper_id=sleeper_id,
        result=result,
        inspector_id=inspector_id,
        start=period.start,
        end=period.end,
    )
    return Page(
        items=[InspectionRead.model_validate(i) for i in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionRead,
    summary="Detalhe da inspeção",
    responses={**AUTH, **errors(404)},
)
async def get_inspection(
    inspection_id: uuid.UUID, session: SessionDep, _: Reader
) -> InspectionRead:
    return InspectionRead.model_validate(await inspection_service.get(session, inspection_id))
