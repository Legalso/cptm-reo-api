"""Importa todos os modelos para registrá-los no metadata (Alembic e testes)."""

from app.models.audit_log import AuditLog
from app.models.inspection import Inspection
from app.models.inventory import InventoryCount
from app.models.location import Location
from app.models.movement import Movement
from app.models.occurrence import Occurrence
from app.models.sleeper import Sleeper
from app.models.species import WoodSpecies
from app.models.sync_batch import SyncBatch
from app.models.user import User

__all__ = [
    "AuditLog",
    "Inspection",
    "InventoryCount",
    "Location",
    "Movement",
    "Occurrence",
    "Sleeper",
    "SyncBatch",
    "User",
    "WoodSpecies",
]
