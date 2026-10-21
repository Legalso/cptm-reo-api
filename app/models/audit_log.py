"""Trilha de auditoria de toda escrita relevante."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Quem fez o quê, quando, em qual entidade, com retrato antes/depois."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_entity_id", "entity", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    # Nulo quando a ação é do sistema (ex.: seed).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
