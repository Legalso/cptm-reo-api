"""Locais físicos: pátio/armazém e ruas dentro dele."""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import LocationKind


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Nó da hierarquia `warehouse` → `street`."""

    __tablename__ = "locations"
    __table_args__ = (
        # Nome único entre irmãos; NULLS NOT DISTINCT cobre os pátios (sem pai).
        UniqueConstraint("parent_id", "name", postgresql_nulls_not_distinct=True),
    )

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[LocationKind] = mapped_column(enum_type(LocationKind, "location_kind"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
