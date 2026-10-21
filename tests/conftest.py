"""Fixtures globais: banco de teste com rollback por teste e cliente HTTP."""

import os
from collections.abc import AsyncIterator

# O app lê a config na importação: aponta para o banco de teste antes de tudo.
os.environ["APP_ENV"] = "test"
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+asyncpg://reo:reo@localhost:5433/reo_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("JWT_SECRET", "segredo-de-teste-" + "x" * 48)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.models  # noqa: E402,F401  (registra todos os modelos no metadata)
from app.api.deps import get_session  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Recria o schema uma vez por sessão de testes."""
    eng = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sessão dentro de uma transação externa desfeita ao fim do teste.

    `create_savepoint` faz os `commit()` dos services virarem savepoints, então
    nada do teste vaza para o próximo.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        sess = AsyncSession(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield sess
        finally:
            await sess.close()
            await trans.rollback()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP falando com o app em memória, usando a sessão do teste."""
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
