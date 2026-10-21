"""Schemas de inspeção digital."""

import uuid
from datetime import datetime

from pydantic import ConfigDict
from pydantic.config import JsonDict

from app.models.enums import ConservationState, InspectionResult, MoistureLevel
from app.schemas.common import ORMModel

INSPECTION_EXAMPLE: JsonDict = {
    "id": "4f3e2d1c-0b9a-4876-8543-210fedcba987",
    "sleeper_id": "3e2d1c0b-a9f8-4e7d-b6c5-a4b3c2d1e0f9",
    "inspector_id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
    "inspected_at": "2026-10-21T14:00:00Z",
    "conservation": "fair",
    "has_cracks": True,
    "biological_attack": False,
    "moisture": "dry",
    "estimated_life_years": 8,
    "species_confirmed": True,
    "species_corrected_id": None,
    "notes": "Rachadura superficial na face superior.",
    "result": "approved",
    "duration_seconds": 95,
    "client_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "created_at": "2026-10-21T14:02:00Z",
}


class InspectionRead(ORMModel):
    model_config = ConfigDict(json_schema_extra={"example": INSPECTION_EXAMPLE})

    id: uuid.UUID
    sleeper_id: uuid.UUID
    inspector_id: uuid.UUID
    inspected_at: datetime
    conservation: ConservationState
    has_cracks: bool
    biological_attack: bool
    moisture: MoistureLevel
    estimated_life_years: int | None
    species_confirmed: bool | None
    species_corrected_id: uuid.UUID | None
    notes: str | None
    result: InspectionResult
    duration_seconds: int | None
    client_uuid: uuid.UUID | None
    created_at: datetime
