"""Schemas de usuários, papéis e convites."""

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from app.models.enums import Role
from app.schemas.common import ORMModel


def _normalize_role(value: object) -> object:
    """Aceita o papel sem diferenciar maiúsculas/acentos ("Técnico" → "tecnico")."""
    if isinstance(value, str):
        decomposed = unicodedata.normalize("NFKD", value.strip().lower())
        return "".join(c for c in decomposed if not unicodedata.combining(c))
    return value


RoleInput = Annotated[Role, BeforeValidator(_normalize_role)]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Registration = Annotated[str, Field(min_length=2, max_length=40, examples=["RL-8842"])]


class UserRead(ORMModel):
    """Usuário sem dados sensíveis (o hash da senha nunca sai da API)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                "name": "Ana Giulia",
                "email": "ana.giulia@cptm.sp.gov.br",
                "registration": "RL-8842",
                "role": "tecnico",
                "active": True,
                "created_at": "2026-10-21T22:00:00Z",
                "updated_at": "2026-10-21T22:00:00Z",
            }
        }
    )

    id: uuid.UUID
    name: str
    email: str
    registration: str
    role: Role
    active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Cadastro direto de usuário pelo admin."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Fernanda Rocha",
                "email": "fernanda.rocha@cptm.sp.gov.br",
                "registration": "RL-9001",
                "password": "Senha-forte-123",
                "role": "operador",
            }
        },
    )

    name: str = Field(min_length=2, max_length=120, validation_alias=AliasChoices("name", "nome"))
    email: EmailStr
    registration: Registration = Field(validation_alias=AliasChoices("registration", "matricula"))
    password: Password = Field(validation_alias=AliasChoices("password", "senha"))
    role: RoleInput = Field(validation_alias=AliasChoices("role", "papel"))


class RoleUpdate(BaseModel):
    """Troca de papel (`PATCH /usuarios/{id}/papel`)."""

    model_config = ConfigDict(
        populate_by_name=True, json_schema_extra={"example": {"role": "supervisor"}}
    )

    role: RoleInput = Field(validation_alias=AliasChoices("role", "papel"))


class InviteCreate(BaseModel):
    """Convite para quem ainda não tem conta.

    Aceita os nomes de campo que o site já envia (`nome`, `papel`); o `link`
    que o site manda é ignorado — token e link são gerados aqui.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Marcos Vinícius",
                "email": "marcos@cptm.sp.gov.br",
                "role": "tecnico",
            }
        },
    )

    name: str = Field(min_length=2, max_length=120, validation_alias=AliasChoices("name", "nome"))
    email: EmailStr
    role: RoleInput = Field(validation_alias=AliasChoices("role", "papel"))
    registration: Registration | None = Field(
        default=None, validation_alias=AliasChoices("registration", "matricula")
    )


class InviteRead(BaseModel):
    """Convite gerado; o site abre o mailto com o `link` (sem envio de e-mail pela API)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "marcos@cptm.sp.gov.br",
                "name": "Marcos Vinícius",
                "role": "tecnico",
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "link": "https://mplihd.github.io/convite/eyJhbGciOiJIUzI1NiIs...",
                "expires_at": "2026-10-24T22:00:00Z",
            }
        }
    )

    email: str
    name: str
    role: Role
    token: str
    link: str
    expires_at: datetime


class InviteAccept(BaseModel):
    """Aceite do convite: a pessoa define a senha (e a matrícula, se o convite não trouxe)."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "password": "Senha-forte-123",
                "registration": "RL-9002",
            }
        },
    )

    token: str = Field(min_length=10)
    password: Password = Field(validation_alias=AliasChoices("password", "senha"))
    registration: Registration | None = Field(
        default=None, validation_alias=AliasChoices("registration", "matricula")
    )
