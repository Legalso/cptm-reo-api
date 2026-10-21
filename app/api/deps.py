"""Dependências compartilhadas pelas rotas (sessão, usuário atual, papéis)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import SessionFactory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Uma sessão por requisição; os services decidem quando fazer commit."""
    async with SessionFactory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
