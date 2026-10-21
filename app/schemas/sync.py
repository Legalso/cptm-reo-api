"""Schemas da sincronização offline (lote misto do app)."""

import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.config import JsonDict

from app.models.enums import SyncBatchStatus, SyncItemStatus
from app.schemas.common import ORMModel

MAX_BATCH_ITEMS = 1000

ItemType = Literal["movement", "inspection", "occurrence", "inventory_count"]

_TAG = "E2801160600002084E5A1B21"
_LOCATION = "5a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d"

_REQUEST_EXAMPLE: JsonDict = {
    "device_id": "coletor-07",
    "movements": [
        {
            "client_uuid": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
            "rfid_tag": _TAG,
            "kind": "transfer",
            "to_location_id": _LOCATION,
            "occurred_at": "2026-10-21T13:05:00Z",
        }
    ],
    "inspections": [
        {
            "client_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "rfid_tag": _TAG,
            "inspected_at": "2026-10-21T13:20:00Z",
            "conservation": "good",
            "has_cracks": False,
            "biological_attack": False,
            "moisture": "dry",
            "result": "approved",
            "duration_seconds": 80,
        }
    ],
    "occurrences": [],
    "inventory_counts": [],
}

_ITEMS_DOC = (
    "Cada item segue o mesmo schema do POST direto ({}), com `client_uuid` obrigatório. "
    "Itens inválidos são rejeitados individualmente, sem derrubar o lote."
)


class SyncBatchRequest(BaseModel):
    """Lote enviado pelo app ao reconectar.

    Os itens são processados em ordem cronológica (data do evento), independente
    da lista em que vieram — ex.: a reprovação feita antes de uma transferência
    é aplicada antes dela.
    """

    model_config = ConfigDict(json_schema_extra={"example": _REQUEST_EXAMPLE})

    device_id: str | None = Field(
        default=None, max_length=120, description="Identificador do aparelho"
    )
    # Itens chegam crus: a validação é por item, para um item ruim não derrubar o lote.
    movements: list[dict[str, Any]] = Field(
        default_factory=list, description=_ITEMS_DOC.format("POST /estoque/movimentacao")
    )
    inspections: list[dict[str, Any]] = Field(
        default_factory=list, description=_ITEMS_DOC.format("POST /inspecoes")
    )
    occurrences: list[dict[str, Any]] = Field(
        default_factory=list, description=_ITEMS_DOC.format("POST /estoque/ocorrencias")
    )
    inventory_counts: list[dict[str, Any]] = Field(
        default_factory=list, description=_ITEMS_DOC.format("POST /estoque/inventario")
    )

    @model_validator(mode="after")
    def _limit_size(self) -> Self:
        total = (
            len(self.movements)
            + len(self.inspections)
            + len(self.occurrences)
            + len(self.inventory_counts)
        )
        if total > MAX_BATCH_ITEMS:
            raise ValueError(f"lote com mais de {MAX_BATCH_ITEMS} itens; divida em partes")
        return self


class SyncItemResult(BaseModel):
    """Resultado de um item: `index` é a posição dele na lista de origem."""

    type: ItemType
    index: int
    client_uuid: uuid.UUID | None
    status: SyncItemStatus
    id: uuid.UUID | None = Field(default=None, description="Registro criado/existente no servidor")
    code: str | None = Field(default=None, description="Código do erro quando rejeitado")
    reason: str | None = Field(default=None, description="Motivo legível quando rejeitado")


_RESULT_EXAMPLE: JsonDict = {
    "id": "8e7d6c5b-4a39-4281-9f0e-1d2c3b4a5f6e",
    "device_id": "coletor-07",
    "received_at": "2026-10-21T18:00:00Z",
    "total": 3,
    "accepted": 1,
    "duplicate": 1,
    "rejected": 1,
    "status": "partial",
    "results": [
        {
            "type": "movement",
            "index": 0,
            "client_uuid": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
            "status": "accepted",
            "id": "9c8b7a6d-5e4f-4321-9abc-def012345678",
            "code": None,
            "reason": None,
        },
        {
            "type": "inspection",
            "index": 0,
            "client_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "status": "duplicate",
            "id": "4f3e2d1c-0b9a-4876-8543-210fedcba987",
            "code": None,
            "reason": None,
        },
        {
            "type": "movement",
            "index": 1,
            "client_uuid": "6fa459ea-ee8a-3ca4-894e-db77e160355e",
            "status": "rejected",
            "id": None,
            "code": "sleeper_discarded",
            "reason": "Dormente descartado não movimenta.",
        },
    ],
}


class SyncBatchRead(ORMModel):
    """Resumo do lote + resultado por item."""

    model_config = ConfigDict(json_schema_extra={"example": _RESULT_EXAMPLE})

    id: uuid.UUID
    device_id: str | None
    received_at: datetime
    total: int
    accepted: int
    duplicate: int
    rejected: int
    status: SyncBatchStatus
    results: list[SyncItemResult]


class SyncStatusRead(BaseModel):
    """Último lote do usuário (e do aparelho, se informado); `null` se nunca sincronizou."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"last_batch": _RESULT_EXAMPLE, "server_time": "2026-10-21T18:05:00Z"}
        }
    )

    last_batch: SyncBatchRead | None
    server_time: datetime
