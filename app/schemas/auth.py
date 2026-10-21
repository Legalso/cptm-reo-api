"""Schemas de autenticação."""

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """`login` aceita matrícula **ou** e-mail."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"login": "RL-8842", "password": "Senha-forte-123"}},
    )

    login: str = Field(
        min_length=2,
        max_length=254,
        validation_alias=AliasChoices("login", "usuario", "email", "registration", "matricula"),
    )
    password: str = Field(
        min_length=1, max_length=128, validation_alias=AliasChoices("password", "senha")
    )


class RefreshRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"refresh_token": "eyJhbGciOi..."}})

    refresh_token: str = Field(min_length=10)


class TokenResponse(BaseModel):
    """Par de tokens + usuário logado."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "expires_at": "2026-10-21T22:15:00Z",
                "refresh_expires_at": "2026-10-28T22:00:00Z",
                "user": {
                    "id": "6f1c1f2e-8f0a-4c8e-9a3f-2b7d6c1e4a10",
                    "name": "Ana Giulia",
                    "email": "ana.giulia@cptm.sp.gov.br",
                    "registration": "RL-8842",
                    "role": "tecnico",
                    "active": True,
                    "created_at": "2026-10-21T22:00:00Z",
                    "updated_at": "2026-10-21T22:00:00Z",
                },
            }
        }
    )

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    refresh_expires_at: datetime
    user: UserRead
