"""Consultas da trilha de auditoria."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.audit_log import AuditLog
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def list_logs(
    session: AsyncSession,
    page: PageParams,
    *,
    user_id: uuid.UUID | None,
    entity: str | None,
    entity_id: uuid.UUID | None,
    action: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[AuditLog], int]:
    stmt = (
        select(AuditLog)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if entity is not None:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if start is not None:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end is not None:
        stmt = stmt.where(AuditLog.created_at < end)
    return await paginate(session, stmt, page)
