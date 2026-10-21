"""Usuários do sistema."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, enum_type
from app.models.enums import Role


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Operador, técnico, especialista, supervisor ou admin."""

    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120))
    # E-mail e matrícula são gravados normalizados (minúsculo / maiúsculo) pelo service.
    email: Mapped[str] = mapped_column(String(254), unique=True)
    registration: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_type(Role, "user_role"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
