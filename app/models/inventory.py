"""Contagem de inventário (espelha a ficha de papel)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InventoryCount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Quantidade contada por local + espécie, com tags lidas opcionais."""

    __tablename__ = "inventory_counts"
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_non_negative"),)

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    species_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wood_species.id", ondelete="RESTRICT"), index=True
    )
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    # TODO(decidir): regra de conciliação contagem física x sistema. Por ora só guardamos.
    read_tags: Mapped[list[str] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
