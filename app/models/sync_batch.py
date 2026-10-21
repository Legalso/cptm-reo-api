"""Registro de cada lote de sincronização recebido do app."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import SyncBatchStatus


class SyncBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_batches"
    __table_args__ = (
        # Consulta típica: último lote do usuário (e do aparelho).
        Index("ix_sync_batches_user_device_received", "user_id", "device_id", "received_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    device_id: Mapped[str | None] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[int] = mapped_column(Integer)
    duplicate: Mapped[int] = mapped_column(Integer)
    rejected: Mapped[int] = mapped_column(Integer)
    status: Mapped[SyncBatchStatus] = mapped_column(enum_type(SyncBatchStatus, "sync_status"))
    # Resultado por item, para o app poder reconsultar o que foi rejeitado.
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
