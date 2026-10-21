"""Schemas compartilhados: paginação e erro padrão."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _to_utc(value: datetime) -> datetime:
    """Data sem fuso é tratada como UTC; com fuso é convertida para UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]


def normalize_tag(value: str) -> str:
    """Tag RFID sem espaços e em maiúsculas: o mesmo código lido de formas diferentes casa."""
    return value.strip().upper()


RfidTag = Annotated[
    str,
    Field(
        min_length=1, max_length=64, pattern=r"^\s*\S+\s*$", examples=["E2801160600002084E5A1B21"]
    ),
    AfterValidator(normalize_tag),
]


@dataclass(frozen=True)
class PageParams:
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class Period:
    """Intervalo [start, end) em UTC; None = aberto."""

    start: datetime | None = None
    end: datetime | None = None


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


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(ErrorResponse):
    """422: mesmo formato padrão, com a lista de campos inválidos em `errors`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Dados inválidos em 'quantity': Input should be greater than or equal to 0",  # noqa: E501
                "code": "validation_error",
                "errors": [
                    {
                        "loc": ["body", "quantity"],
                        "msg": "Input should be greater than or equal to 0",
                        "type": "greater_than_equal",
                    }
                ],
            }
        }
    )

    errors: list[FieldError] = []


class ORMModel(BaseModel):
    """Base dos schemas de saída montados a partir de modelos ORM."""

    model_config = ConfigDict(from_attributes=True)
