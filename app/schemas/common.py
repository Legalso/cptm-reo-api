"""Schemas compartilhados: paginação e erro padrão."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


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
