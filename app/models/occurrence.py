"""Ocorrências de campo (dano, perda, extravio...)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import OccurrenceKind


class Occurrence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "occurrences"

    sleeper_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sleepers.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[OccurrenceKind] = mapped_column(
        enum_type(OccurrenceKind, "occurrence_kind"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
