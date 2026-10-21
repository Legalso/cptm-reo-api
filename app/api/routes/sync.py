"""Sincronização offline do app."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, require_roles
from app.api.responses import AUTH, AUTH_VALIDATION
from app.core.permissions import ALL_ROLES, FIELD_ROLES
from app.db.mixins import utcnow
from app.models.user import User
from app.schemas.sync import SyncBatchRead, SyncBatchRequest, SyncStatusRead
from app.services import sync as sync_service

router = APIRouter(prefix="/sincronizacao", tags=["Sincronização"])

FieldUser = Annotated[User, Depends(require_roles(*FIELD_ROLES))]
Reader = Annotated[User, Depends(require_roles(*ALL_ROLES))]


@router.post(
    "/replicar",
    response_model=SyncBatchRead,
    summary="Enviar lote offline (movimentações, inspeções, ocorrências, inventário)",
    responses=AUTH_VALIDATION,
)
async def replicate(data: SyncBatchRequest, session: SessionDep, actor: FieldUser) -> SyncBatchRead:
    """Sempre 200 quando o lote é lido: o resultado de cada item vem em `results`
    (`accepted` | `duplicate` | `rejected` + motivo). Reenviar é seguro."""
    batch = await sync_service.replicate(session, data, actor)
    return SyncBatchRead.model_validate(batch)


@router.get(
    "/status",
    response_model=SyncStatusRead,
    summary="Último lote sincronizado pelo usuário",
    responses=AUTH,
)
async def status(
    session: SessionDep,
    actor: Reader,
    device_id: Annotated[
        str | None, Query(max_length=120, description="Filtra pelo aparelho")
    ] = None,
) -> SyncStatusRead:
    batch = await sync_service.latest(session, actor, device_id)
    return SyncStatusRead(
        last_batch=SyncBatchRead.model_validate(batch) if batch else None,
        server_time=utcnow(),
    )
