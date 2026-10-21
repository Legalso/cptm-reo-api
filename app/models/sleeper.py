"""Dormente ferroviário identificado por tag RFID."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import SleeperStatus
from app.models.location import Location
from app.models.species import WoodSpecies


class Sleeper(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Dados da plaqueta física + estado operacional atual."""

    __tablename__ = "sleepers"

    # Caminho mais quente da API: o app consulta por tag a cada leitura.
    rfid_tag: Mapped[str] = mapped_column(String(64), unique=True)
    registration_record: Mapped[str | None] = mapped_column(String(40), index=True)
    # Pode nascer sem espécie: a classificação é papel do especialista.
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wood_species.id", ondelete="RESTRICT"), index=True
    )
    wood_class: Mapped[str | None] = mapped_column(String(10))
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    treatment: Mapped[str | None] = mapped_column(String(40))
    supplier: Mapped[str | None] = mapped_column(String(80))
    inspection_company: Mapped[str | None] = mapped_column(String(80))
    manufacture_year: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[SleeperStatus] = mapped_column(
        enum_type(SleeperStatus, "sleeper_status"), default=SleeperStatus.IN_STOCK, index=True
    )
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True
    )

    # lazy="raise": em sessão async, carregamento implícito quebraria; o repository
    # carrega explicitamente quando precisa.
    species: Mapped[WoodSpecies | None] = relationship(lazy="raise")
    current_location: Mapped[Location | None] = relationship(lazy="raise")
