"""Schemas de entrada das operações de campo (usados na API direta e no sync).

Todo registro aceita `client_uuid` (gerado no aparelho) e a data do evento:
reenviar o mesmo `client_uuid` não duplica nada.
"""

import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    ConservationState,
    InspectionResult,
    MoistureLevel,
    MovementKind,
    OccurrenceKind,
)
from app.schemas.common import RfidTag, UtcDatetime, normalize_tag

ClientUuid = Field(default=None, description="UUID gerado no app (idempotência)")
EventTime = Field(default=None, description="Quando aconteceu (UTC). Padrão: agora")

TAG = "E2801160600002084E5A1B21"
LOCATION = "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
SPECIES = "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21"
CLIENT = "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed"


class SleeperRef(BaseModel):
    """Identifica o dormente por `sleeper_id` **ou** `rfid_tag` (o app normalmente só tem a tag)."""

    sleeper_id: uuid.UUID | None = None
    rfid_tag: RfidTag | None = None

    @model_validator(mode="after")
    def _one_reference(self) -> Self:
        if (self.sleeper_id is None) == (self.rfid_tag is None):
            raise ValueError("informe sleeper_id ou rfid_tag (exatamente um)")
        return self


class MovementCreate(SleeperRef):
    """Entrada exige destino; retirada exige RM; transferência exige destino."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "rfid_tag": TAG,
                    "kind": "withdrawal",
                    "requisition_number": "RM-2026-0042",
                    "occurred_at": "2026-10-21T13:05:00Z",
                    "client_uuid": CLIENT,
                },
                {"rfid_tag": TAG, "kind": "transfer", "to_location_id": LOCATION},
            ]
        }
    )

    kind: MovementKind
    to_location_id: uuid.UUID | None = None
    requisition_number: str | None = Field(default=None, min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    occurred_at: UtcDatetime | None = EventTime
    client_uuid: uuid.UUID | None = ClientUuid

    @model_validator(mode="after")
    def _required_by_kind(self) -> Self:
        if self.kind in (MovementKind.ENTRY, MovementKind.TRANSFER) and not self.to_location_id:
            raise ValueError(f"{self.kind} exige to_location_id")
        if self.kind == MovementKind.WITHDRAWAL:
            if not self.requisition_number:
                raise ValueError("retirada exige requisition_number (RM)")
            if self.to_location_id:
                raise ValueError("retirada não tem destino no estoque")
        return self


class LocationAssign(SleeperRef):
    """Atalho: posiciona o dormente no local (transferência, ou entrada se estava fora)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"rfid_tag": TAG, "location_id": LOCATION, "client_uuid": CLIENT}
        }
    )

    location_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=2000)
    occurred_at: UtcDatetime | None = EventTime
    client_uuid: uuid.UUID | None = ClientUuid


class InventoryCountCreate(BaseModel):
    """Contagem por local + espécie, como na ficha de papel."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "location_id": LOCATION,
                "species_id": SPECIES,
                "quantity": 42,
                "counted_at": "2026-10-21T09:00:00Z",
                "read_tags": [TAG, "E2801160600002084E5A1B22"],
                "notes": "Contagem mensal",
                "client_uuid": CLIENT,
            }
        }
    )

    location_id: uuid.UUID
    species_id: uuid.UUID
    quantity: int = Field(ge=0, le=1_000_000)
    counted_at: UtcDatetime | None = EventTime
    read_tags: list[str] | None = Field(
        default=None, max_length=10_000, description="Tags lidas (opcional, para conciliação)"
    )
    notes: str | None = Field(default=None, max_length=2000)
    client_uuid: uuid.UUID | None = ClientUuid

    @field_validator("read_tags")
    @classmethod
    def _normalize_tags(cls, tags: list[str] | None) -> list[str] | None:
        """Normaliza e remove repetidas mantendo a ordem de leitura."""
        if tags is None:
            return None
        cleaned = [normalize_tag(t) for t in tags if t and t.strip()]
        if any(len(t) > 64 for t in cleaned):
            raise ValueError("tag com mais de 64 caracteres")
        return list(dict.fromkeys(cleaned))


class OccurrenceCreate(BaseModel):
    """Ocorrência; `location_id` é opcional quando o dormente informado está num local."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rfid_tag": TAG,
                "kind": "damage",
                "description": "Dormente rachado durante o manuseio.",
                "occurred_at": "2026-10-21T15:30:00Z",
                "client_uuid": CLIENT,
            }
        }
    )

    sleeper_id: uuid.UUID | None = None
    rfid_tag: RfidTag | None = None
    location_id: uuid.UUID | None = None
    kind: OccurrenceKind
    description: str = Field(min_length=3, max_length=2000)
    occurred_at: UtcDatetime | None = EventTime
    client_uuid: uuid.UUID | None = ClientUuid

    @model_validator(mode="after")
    def _where(self) -> Self:
        if self.sleeper_id and self.rfid_tag:
            raise ValueError("informe sleeper_id ou rfid_tag, não os dois")
        if not (self.sleeper_id or self.rfid_tag or self.location_id):
            raise ValueError("informe o dormente ou o location_id")
        return self


class InspectionCreate(SleeperRef):
    """Checklist de inspeção. Reprovação coloca o dormente em quarentena."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rfid_tag": TAG,
                "inspected_at": "2026-10-21T14:00:00Z",
                "conservation": "fair",
                "has_cracks": True,
                "biological_attack": False,
                "moisture": "dry",
                "estimated_life_years": 8,
                "species_confirmed": True,
                "notes": "Rachadura superficial.",
                "result": "approved",
                "duration_seconds": 95,
                "client_uuid": CLIENT,
            }
        }
    )

    inspected_at: UtcDatetime | None = EventTime
    conservation: ConservationState
    has_cracks: bool
    biological_attack: bool
    moisture: MoistureLevel
    estimated_life_years: int | None = Field(default=None, ge=0, le=100)
    species_confirmed: bool | None = None
    species_corrected_id: uuid.UUID | None = Field(
        default=None, description="Espécie correta; só é aplicada ao dormente por especialista"
    )
    notes: str | None = Field(default=None, max_length=4000)
    result: InspectionResult
    duration_seconds: int | None = Field(default=None, ge=0, le=86_400)
    client_uuid: uuid.UUID | None = ClientUuid

    @model_validator(mode="after")
    def _species_consistency(self) -> Self:
        if self.species_corrected_id and self.species_confirmed:
            raise ValueError("species_corrected_id implica species_confirmed=false")
        return self
