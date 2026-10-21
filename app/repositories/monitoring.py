"""Consultas de saúde do banco."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession


async def ping_database(session: AsyncSession) -> bool:
    """Executa `SELECT 1`; devolve False se o banco não responder."""
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True
