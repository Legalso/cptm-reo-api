"""Schemas do catálogo de espécies."""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.config import JsonDict

from app.schemas.common import ORMModel

_EXAMPLE: JsonDict = {
    "id": "0b8e5f8a-1c2d-4e3f-9a8b-7c6d5e4f3a21",
    "code": "13",
    "scientific_name": "Hymenaea courbaril",
    "common_name": "Jatobá",
    "active": True,
    "created_at": "2026-10-21T22:00:00Z",
    "updated_at": "2026-10-21T22:00:00Z",
}


class SpeciesSummary(ORMModel):
    """Versão curta, embutida no dormente."""

    id: uuid.UUID
    code: str
    scientific_name: str | None
    common_name: str | None


class SpeciesRead(SpeciesSummary):
    model_config = ConfigDict(json_schema_extra={"example": _EXAMPLE})

    active: bool
    created_at: datetime
    updated_at: datetime


class SpeciesCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"code": "23", "scientific_name": "Manilkara huberi", "common_name": None}
        }
    )

    code: str = Field(min_length=1, max_length=10, pattern=r"^\S+$")
    scientific_name: str | None = Field(default=None, max_length=200)
    common_name: str | None = Field(default=None, max_length=120)
    active: bool = True

    @model_validator(mode="after")
    def _has_name(self) -> Self:
        """Ao menos um dos nomes é obrigatório (espelha a CHECK do banco)."""
        if not (self.scientific_name or self.common_name):
            raise ValueError("informe scientific_name ou common_name")
        return self


class SpeciesUpdate(BaseModel):
    """Campos omitidos não mudam."""

    model_config = ConfigDict(json_schema_extra={"example": {"common_name": "Jatobá"}})

    scientific_name: str | None = Field(default=None, max_length=200)
    common_name: str | None = Field(default=None, max_length=120)
    active: bool | None = None
