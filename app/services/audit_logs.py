"""Consulta da trilha de auditoria."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories import audit_logs as audit_repo
from app.schemas.common import PageParams, Period


async def list_logs(
    session: AsyncSession,
    page: PageParams,
    period: Period,
    *,
    user_id: uuid.UUID | None,
    entity: str | None,
    entity_id: uuid.UUID | None,
    action: str | None,
) -> tuple[list[AuditLog], int]:
    return await audit_repo.list_logs(
        session,
        page,
        user_id=user_id,
        entity=entity,
        entity_id=entity_id,
        action=action,
        start=period.start,
        end=period.end,
    )
