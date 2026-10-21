"""Schemas de leitura de movimentações, inventário e ocorrências."""

import uuid
from datetime import datetime

from pydantic import ConfigDict

from app.models.enums import MovementKind, OccurrenceKind
from app.schemas.common import ORMModel


class MovementRead(ORMModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "9c8b7a6d-5e4f-4321-9abc-def012345678",
                "sleeper_id": "3e2d1c0b-a9f8-4e7d-b6c5-a4b3c2d1e0f9",
                "kind": "withdrawal",
                "from_location_id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                "to_location_id": None,
                "requisition_number": "RM-2026-0042",
                "notes": None,
                "user_id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                "occurred_at": "2026-10-21T13:05:00Z",
                "client_uuid": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
                "created_at": "2026-10-21T13:10:00Z",
            }
        }
    )

    id: uuid.UUID
    sleeper_id: uuid.UUID
    kind: MovementKind
    from_location_id: uuid.UUID | None
    to_location_id: uuid.UUID | None
    requisition_number: str | None
    notes: str | None
    user_id: uuid.UUID
    occurred_at: datetime
    client_uuid: uuid.UUID | None
    created_at: datetime


class InventoryCountRead(ORMModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "2a3b4c5d-6e7f-4809-a1b2-c3d4e5f60718",
                "location_id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                "species_id": "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21",
                "counted_at": "2026-10-21T09:00:00Z",
                "quantity": 42,
                "read_tags": ["E2801160600002084E5A1B21", "E2801160600002084E5A1B22"],
                "notes": "Contagem mensal",
                "user_id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                "client_uuid": None,
                "created_at": "2026-10-21T09:05:00Z",
            }
        }
    )

    id: uuid.UUID
    location_id: uuid.UUID
    species_id: uuid.UUID
    counted_at: datetime
    quantity: int
    read_tags: list[str] | None
    notes: str | None
    user_id: uuid.UUID
    client_uuid: uuid.UUID | None
    created_at: datetime


class OccurrenceRead(ORMModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "7d6c5b4a-3928-4170-8f9e-0d1c2b3a4f5e",
                "sleeper_id": None,
                "location_id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                "kind": "damage",
                "description": "Pilha tombada na Rua 08, 3 dormentes rachados.",
                "user_id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                "occurred_at": "2026-10-21T15:30:00Z",
                "client_uuid": None,
                "created_at": "2026-10-21T15:31:00Z",
            }
        }
    )

    id: uuid.UUID
    sleeper_id: uuid.UUID | None
    location_id: uuid.UUID
    kind: OccurrenceKind
    description: str
    user_id: uuid.UUID
    occurred_at: datetime
    client_uuid: uuid.UUID | None
    created_at: datetime
