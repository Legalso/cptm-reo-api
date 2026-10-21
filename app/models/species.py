"""Catálogo de espécies de madeira."""

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WoodSpecies(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Espécie de madeira identificada pelo código da ficha (ex. "01")."""

    __tablename__ = "wood_species"
    __table_args__ = (
        # Itens antigos da ficha (ex. "Coimmal") só têm nome comum.
        CheckConstraint("scientific_name IS NOT NULL OR common_name IS NOT NULL", name="has_name"),
    )

    code: Mapped[str] = mapped_column(String(10), unique=True)
    scientific_name: Mapped[str | None] = mapped_column(String(200))
    common_name: Mapped[str | None] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
