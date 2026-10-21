"""Schemas do dashboard (`GET /indicadores`) e dos logs (`GET /logs`)."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import LocationKind, OccurrenceKind, SleeperStatus
from app.schemas.common import ORMModel


class PeriodRead(BaseModel):
    start: datetime
    end: datetime


class StatusCount(BaseModel):
    status: SleeperStatus
    count: int


class SpeciesCount(BaseModel):
    species_id: uuid.UUID | None
    code: str | None
    name: str
    count: int


class LocationCount(BaseModel):
    location_id: uuid.UUID
    name: str
    kind: LocationKind
    count: int


class MovementsDay(BaseModel):
    day: date
    entry: int
    withdrawal: int
    transfer: int
    total: int


class InspectionsDay(BaseModel):
    day: date
    approved: int
    rejected: int
    total: int


class OccurrenceCount(BaseModel):
    kind: OccurrenceKind
    count: int


class IndicatorsRead(BaseModel):
    """Retratos atuais (`sleepers_by_*`) + métricas do período (`?de=&ate=`)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": {"start": "2026-10-14T22:00:00Z", "end": "2026-10-21T22:00:00Z"},
                "sleepers_total": 120,
                "sleepers_by_status": [
                    {"status": "in_stock", "count": 98},
                    {"status": "withdrawn", "count": 10},
                    {"status": "in_track", "count": 5},
                    {"status": "quarantine", "count": 4},
                    {"status": "discarded", "count": 3},
                ],
                "sleepers_by_species": [
                    {
                        "species_id": "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21",
                        "code": "13",
                        "name": "Hymenaea courbaril",
                        "count": 60,
                    }
                ],
                "sleepers_by_location": [
                    {
                        "location_id": "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
                        "name": "Rua 08",
                        "kind": "street",
                        "count": 102,
                    }
                ],
                "movements_per_day": [
                    {"day": "2026-10-21", "entry": 3, "withdrawal": 2, "transfer": 1, "total": 6}
                ],
                "inspections_per_day": [
                    {"day": "2026-10-21", "approved": 7, "rejected": 1, "total": 8}
                ],
                "inspections_total": 8,
                "average_inspection_seconds": 92.5,
                "rejection_rate": 0.125,
                "occurrences_by_kind": [
                    {"kind": "damage", "count": 2},
                    {"kind": "loss", "count": 1},
                    {"kind": "misplaced", "count": 0},
                    {"kind": "other", "count": 0},
                ],
                "losses": 1,
            }
        }
    )

    period: PeriodRead
    sleepers_total: int
    sleepers_by_status: list[StatusCount]
    sleepers_by_species: list[SpeciesCount]
    sleepers_by_location: list[LocationCount]
    movements_per_day: list[MovementsDay]
    inspections_per_day: list[InspectionsDay]
    inspections_total: int
    average_inspection_seconds: float | None
    rejection_rate: float | None
    occurrences_by_kind: list[OccurrenceCount]
    losses: int


class AuditUser(ORMModel):
    id: uuid.UUID
    name: str
    registration: str


class AuditLogRead(ORMModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "aa1b2c3d-4e5f-4061-8728-394a5b6c7d8e",
                "user": {
                    "id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                    "name": "Ana Giulia",
                    "registration": "RL-8842",
                },
                "action": "change_role",
                "entity": "user",
                "entity_id": "7b6a5c4d-3e2f-4109-8a7b-6c5d4e3f2a1b",
                "before": {"role": "operador"},
                "after": {"role": "tecnico"},
                "created_at": "2026-10-21T18:30:00Z",
            }
        }
    )

    id: uuid.UUID
    user: AuditUser | None
    action: str
    entity: str
    entity_id: uuid.UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime
