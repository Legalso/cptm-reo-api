"""Inspeção digital de dormente (checklist)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import ConservationState, InspectionResult, MoistureLevel


class Inspection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inspections"

    sleeper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sleepers.id", ondelete="RESTRICT"), index=True
    )
    inspector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    conservation: Mapped[ConservationState] = mapped_column(
        enum_type(ConservationState, "conservation_state")
    )
    has_cracks: Mapped[bool] = mapped_column(Boolean)
    biological_attack: Mapped[bool] = mapped_column(Boolean)
    moisture: Mapped[MoistureLevel] = mapped_column(enum_type(MoistureLevel, "moisture_level"))
    estimated_life_years: Mapped[int | None] = mapped_column(SmallInteger)
    species_confirmed: Mapped[bool | None] = mapped_column(Boolean)
    species_corrected_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wood_species.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    result: Mapped[InspectionResult] = mapped_column(
        enum_type(InspectionResult, "inspection_result"), index=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    client_uuid: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
