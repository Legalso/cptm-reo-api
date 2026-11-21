"""Dashboard gerencial (supervisor e admin) e trilha de auditoria (só admin)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import PageDep, PeriodDep, SessionDep, require_roles
from app.api.responses import AUTH, errors
from app.core.permissions import ADMIN_ONLY, MANAGEMENT_ROLES
from app.models.user import User
from app.schemas.common import Page
from app.schemas.indicators import AuditLogRead, IndicatorsRead
from app.services import audit_logs as audit_log_service
from app.services import indicators as indicator_service

router = APIRouter(tags=["Indicadores e logs"])

Manager = Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))]
# Auditoria mostra antes/depois de toda escrita (inclusive de usuários): só admin
# (decisão de 2026-11-20; antes o supervisor também lia).
Admin = Annotated[User, Depends(require_roles(*ADMIN_ONLY))]


@router.get(
    "/indicadores",
    response_model=IndicatorsRead,
    summary="Indicadores do dashboard (padrão: últimos 7 dias)",
    responses={**AUTH, **errors(422)},
)
async def get_indicators(session: SessionDep, _: Manager, period: PeriodDep) -> IndicatorsRead:
    """`sleepers_by_*` são o retrato atual; o resto respeita `?de=&ate=`."""
    return await indicator_service.get_indicators(session, period)


@router.get(
    "/logs",
    response_model=Page[AuditLogRead],
    summary="Logs de auditoria (só admin)",
    responses={**AUTH, **errors(422)},
)
async def list_logs(
    session: SessionDep,
    _: Admin,
    page: PageDep,
    period: PeriodDep,
    user_id: Annotated[uuid.UUID | None, Query(description="Quem fez")] = None,
    entity: Annotated[
        str | None, Query(max_length=60, description="Ex.: sleeper, movement, user")
    ] = None,
    entity_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[
        str | None, Query(max_length=40, description="Ex.: create, update, change_role")
    ] = None,
) -> Page[AuditLogRead]:
    items, total = await audit_log_service.list_logs(
        session,
        page,
        period,
        user_id=user_id,
        entity=entity,
        entity_id=entity_id,
        action=action,
    )
    return Page(
        items=[AuditLogRead.model_validate(log) for log in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
