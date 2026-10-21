"""Commit idempotente por `client_uuid`.

Analogia do CONTEXTO: número de rastreio — se o carteiro passar duas vezes,
o pacote não vira dois.
"""

from collections.abc import Awaitable, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError


async def commit_idempotent[T](
    session: AsyncSession,
    apply: Callable[[], Awaitable[tuple[T, bool]]],
    find_existing: Callable[[], Awaitable[T | None]],
) -> tuple[T, bool]:
    """Aplica e faz commit; se outra requisição gravou o mesmo client_uuid no meio
    do caminho (violação de unique), devolve o registro dela como duplicado."""
    try:
        result = await apply()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        existing = await find_existing()
        if existing is None:
            raise ConflictError("Registro conflitante.", code="conflict") from exc
        return existing, False
    return result
