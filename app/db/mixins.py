"""Mixins de colunas comuns e helper de enum."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Agora em UTC com fuso (todas as datas da API são UTC)."""
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    # Default no Python (além do servidor) para o valor já estar no objeto após o flush,
    # sem refresh — evita lazy load implícito em sessão async.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )


def enum_type(enum_cls: type[StrEnum], name: str) -> Enum:
    """Enum gravado como VARCHAR + CHECK (e não tipo nativo do Postgres).

    Decisão: adicionar valor novo vira só trocar a CHECK numa migration, sem o
    `ALTER TYPE ... ADD VALUE` (que não roda dentro de transação).
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )
