"""Schemas compartilhados: paginação e erro padrão."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def _to_utc(value: datetime) -> datetime:
    """Data sem fuso é tratada como UTC; com fuso é convertida para UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]


@dataclass(frozen=True)
class PageParams:
    limit: int = 50
    offset: int = 0


class Page[T](BaseModel):
    """Envelope de toda listagem paginada."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """Formato único de erro da API."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"detail": "Recurso não encontrado.", "code": "not_found"}}
    )

    detail: str
    code: str


class ORMModel(BaseModel):
    """Base dos schemas de saída montados a partir de modelos ORM."""

    model_config = ConfigDict(from_attributes=True)
