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


async def update_with_audit(
    session: AsyncSession,
    obj: Base,
    changes: dict[str, Any],
    *,
    actor_id: uuid.UUID,
    entity: str,
    action: str = "update",
) -> bool:
    """Aplica `changes` no objeto e audita antes/depois; devolve False se nada mudou."""
    changed = {k: v for k, v in changes.items() if getattr(obj, k) != v}
    if not changed:
        return False
    before = snapshot(obj)
    for key, value in changed.items():
        setattr(obj, key, value)
    await session.flush()
    await record(
        session,
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=getattr(obj, "id", None),
        before=before,
        after=snapshot(obj),
    )
    return True


async def create_with_audit(
    session: AsyncSession, obj: Base, *, actor_id: uuid.UUID | None, entity: str
) -> None:
    """Insere o objeto e audita a criação."""
    session.add(obj)
    await session.flush()
    await record(
        session,
        actor_id=actor_id,
        action="create",
        entity=entity,
        entity_id=getattr(obj, "id", None),
        after=snapshot(obj),
    )


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
