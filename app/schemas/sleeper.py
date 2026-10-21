"""Schemas de dormentes e do histórico."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from app.models.enums import SleeperStatus
from app.schemas.common import ORMModel, RfidTag, UtcDatetime
from app.schemas.inspection import InspectionRead
from app.schemas.location import LocationSummary
from app.schemas.species import SpeciesSummary
from app.schemas.stock import MovementRead, OccurrenceRead

_SLEEPER_EXAMPLE: JsonDict = {
    "id": "3e2d1c0b-a9f8-4e7d-b6c5-a4b3c2d1e0f9",
    "rfid_tag": "E2801160600002084E5A1B21",
    "registration_record": "AR00224-02",
    "species": {
        "id": "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21",
        "code": "13",
        "scientific_name": "Hymenaea courbaril",
        "common_name": None,
    },
    "wood_class": "1a",
    "length_m": "2.80",
    "treatment": "CCA",
    "supplier": "Granoski",
    "inspection_company": "IPT",
    "manufacture_year": 2024,
    "status": "in_stock",
    "current_location": {
        "id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
        "name": "Rua 08",
        "kind": "street",
        "parent_id": "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9",
    },
    "created_at": "2026-10-21T22:00:00Z",
    "updated_at": "2026-10-21T22:00:00Z",
}


class _PlateFields(BaseModel):
    """Campos da plaqueta física do dormente."""

    registration_record: str | None = Field(default=None, max_length=40)
    wood_class: str | None = Field(default=None, max_length=10)
    length_m: Decimal | None = Field(default=None, gt=0, max_digits=4, decimal_places=2)
    treatment: str | None = Field(default=None, max_length=40)
    supplier: str | None = Field(default=None, max_length=80)
    inspection_company: str | None = Field(default=None, max_length=80)
    manufacture_year: int | None = Field(default=None, ge=1900, le=2100)


class SleeperRead(ORMModel):
    model_config = ConfigDict(json_schema_extra={"example": _SLEEPER_EXAMPLE})

    id: uuid.UUID
    rfid_tag: str
    registration_record: str | None
    species: SpeciesSummary | None
    wood_class: str | None
    length_m: Decimal | None
    treatment: str | None
    supplier: str | None
    inspection_company: str | None
    manufacture_year: int | None
    status: SleeperStatus
    current_location: LocationSummary | None
    created_at: datetime
    updated_at: datetime


class SleeperCreate(_PlateFields):
    """Cadastro de dormente novo (tag ainda desconhecida): gera a movimentação de entrada."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rfid_tag": "E2801160600002084E5A1B21",
                "registration_record": "AR00224-02",
                "species_id": "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21",
                "wood_class": "1a",
                "length_m": 2.80,
                "treatment": "CCA",
                "supplier": "Granoski",
                "manufacture_year": 2024,
                "location_id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                "occurred_at": "2026-10-21T13:00:00Z",
                "client_uuid": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
            }
        }
    )

    rfid_tag: RfidTag
    species_id: uuid.UUID | None = None
    location_id: uuid.UUID = Field(description="Onde o dormente está entrando")
    occurred_at: UtcDatetime | None = Field(default=None, description="Padrão: agora (UTC)")
    client_uuid: uuid.UUID | None = Field(
        default=None, description="UUID gerado no app; reenvio devolve o mesmo dormente"
    )


class SleeperUpdate(_PlateFields):
    """Edição parcial. `species_id` exige especialista; `status`, técnico ou acima.

    Status manual permitido: in_stock ↔ quarantine, withdrawn → in_track e
    qualquer → discarded. Entrada/retirada/transferência usam `/estoque/...`.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"wood_class": "1b", "status": "discarded"}}
    )

    rfid_tag: RfidTag | None = None
    species_id: uuid.UUID | None = None
    status: SleeperStatus | None = None


class HistoryEntry(BaseModel):
    """Evento do histórico; só o campo correspondente a `type` vem preenchido."""

    type: Literal["movement", "inspection", "occurrence"]
    occurred_at: datetime
    movement: MovementRead | None = None
    inspection: InspectionRead | None = None
    occurrence: OccurrenceRead | None = None


class SleeperHistory(BaseModel):
    """Linha do tempo do dormente, em ordem cronológica."""

    sleeper: SleeperRead
    items: list[HistoryEntry]
