"""Auditoria: toda escrita relevante passa por `record`."""

import uuid
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models.audit_log import AuditLog

# Nunca vai para o log, nem mascarado.
SENSITIVE_FIELDS = frozenset({"password_hash"})


def snapshot(obj: Base) -> dict[str, Any]:
    """Retrato JSON das colunas de um modelo, sem campos sensíveis."""
    data = {
        column.key: getattr(obj, column.key)
        for column in obj.__table__.columns
        if column.key not in SENSITIVE_FIELDS
    }
    result: dict[str, Any] = to_jsonable_python(data)
    return result


async def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Adiciona o registro na transação corrente (commit fica com quem chamou)."""
    session.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
        )
    )
