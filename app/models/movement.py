"""Movimentações de estoque (entrada, retirada, transferência)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import MovementKind


class Movement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "movements"

    sleeper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sleepers.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[MovementKind] = mapped_column(enum_type(MovementKind, "movement_kind"))
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    requisition_number: Mapped[str | None] = mapped_column(String(40))  # RM, na retirada
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Gerado no aparelho; garante idempotência do sync offline.
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
