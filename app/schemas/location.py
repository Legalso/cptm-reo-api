"""Schemas de locais (pátio → rua)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LocationKind
from app.schemas.common import ORMModel

Latitude = Field(default=None, ge=-90, le=90)
Longitude = Field(default=None, ge=-180, le=180)


class LocationSummary(ORMModel):
    """Versão curta, embutida no dormente."""

    id: uuid.UUID
    name: str
    kind: LocationKind
    parent_id: uuid.UUID | None


class LocationRead(LocationSummary):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                "name": "Rua 08",
                "kind": "street",
                "parent_id": "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9",
                "latitude": -23.5275,
                "longitude": -46.6658,
                "active": True,
                "created_at": "2026-10-21T22:00:00Z",
                "updated_at": "2026-10-21T22:00:00Z",
            }
        }
    )

    latitude: float | None
    longitude: float | None
    active: bool
    created_at: datetime
    updated_at: datetime


class LocationCreate(BaseModel):
    """`street` exige `parent_id` de um `warehouse`; `warehouse` não tem pai."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Rua 09",
                "kind": "street",
                "parent_id": "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9",
            }
        }
    )

    name: str = Field(min_length=1, max_length=120)
    kind: LocationKind
    parent_id: uuid.UUID | None = None
    latitude: float | None = Latitude
    longitude: float | None = Longitude


class LocationUpdate(BaseModel):
    """Tipo e pai são fixos após a criação; campos omitidos não mudam."""

    model_config = ConfigDict(json_schema_extra={"example": {"active": False}})

    name: str | None = Field(default=None, min_length=1, max_length=120)
    latitude: float | None = Latitude
    longitude: float | None = Longitude
    active: bool | None = None
