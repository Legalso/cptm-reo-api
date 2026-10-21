"""Enums de domínio, compartilhados por modelos e schemas.

Valores em minúsculas e estáveis: são gravados no banco e trafegam no JSON.
"""

from enum import StrEnum


class Role(StrEnum):
    """Papéis de acesso (RBAC) — valores em PT, como no contrato com o front."""

    OPERATOR = "operador"
    TECHNICIAN = "tecnico"
    SPECIALIST = "especialista"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class LocationKind(StrEnum):
    WAREHOUSE = "warehouse"  # pátio / armazém
    STREET = "street"  # rua dentro do pátio


class SleeperStatus(StrEnum):
    IN_STOCK = "in_stock"
    WITHDRAWN = "withdrawn"  # retirado para a via
    IN_TRACK = "in_track"
    QUARANTINE = "quarantine"
    DISCARDED = "discarded"


class MovementKind(StrEnum):
    ENTRY = "entry"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"


class ConservationState(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class MoistureLevel(StrEnum):
    DRY = "dry"
    MOIST = "moist"
    WET = "wet"


class InspectionResult(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class OccurrenceKind(StrEnum):
    DAMAGE = "damage"
    LOSS = "loss"
    MISPLACED = "misplaced"
    OTHER = "other"


class SyncBatchStatus(StrEnum):
    COMPLETED = "completed"  # nenhum item rejeitado
    PARTIAL = "partial"  # parte rejeitada
    FAILED = "failed"  # todos rejeitados


class SyncItemStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
