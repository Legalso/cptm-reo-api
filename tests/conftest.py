"""Fixtures globais: banco de teste com rollback por teste e cliente HTTP."""

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

# O app lê a config na importação: aponta para o banco de teste antes de tudo.
os.environ["APP_ENV"] = "test"
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+asyncpg://reo:reo@localhost:5433/reo_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("JWT_SECRET", "segredo-de-teste-" + "x" * 48)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.models.all  # noqa: E402,F401  (registra todos os modelos no metadata)
from app.api.deps import get_session  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.enums import LocationKind, Role, SleeperStatus  # noqa: E402
from app.models.location import Location  # noqa: E402
from app.models.sleeper import Sleeper  # noqa: E402
from app.models.species import WoodSpecies  # noqa: E402
from app.models.user import User  # noqa: E402


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


DEFAULT_PASSWORD = "Senha-forte-123"


class UserFactory(Protocol):
    async def __call__(
        self, role: Role = ..., *, active: bool = ..., password: str = ...
    ) -> User: ...


@pytest.fixture
def make_user(session: AsyncSession) -> UserFactory:
    """Cria usuários direto no banco (sem passar pela API)."""

    async def _make(
        role: Role = Role.OPERATOR, *, active: bool = True, password: str = DEFAULT_PASSWORD
    ) -> User:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            name=f"Usuário {suffix}",
            email=f"user-{suffix}@reo.local",
            registration=f"T-{suffix}".upper(),
            password_hash=hash_password(password),
            role=role,
            active=active,
        )
        session.add(user)
        await session.flush()
        return user

    return _make


def auth_headers(user: User) -> dict[str, str]:
    """Header Authorization com access token válido para o usuário."""
    token, _ = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(make_user: UserFactory) -> User:
    return await make_user(Role.ADMIN)


@pytest.fixture
def admin_headers(admin: User) -> dict[str, str]:
    return auth_headers(admin)


@dataclass
class Catalog:
    species: WoodSpecies
    warehouse: Location
    street: Location
    other_street: Location


@pytest.fixture
async def catalog(session: AsyncSession) -> Catalog:
    """Espécie + pátio com duas ruas, criados direto no banco."""
    species = WoodSpecies(code="13", scientific_name="Hymenaea courbaril")
    warehouse = Location(name="TG – Três Guri", kind=LocationKind.WAREHOUSE)
    session.add_all([species, warehouse])
    await session.flush()
    street = Location(name="Rua 08", kind=LocationKind.STREET, parent_id=warehouse.id)
    other = Location(name="Rua 09", kind=LocationKind.STREET, parent_id=warehouse.id)
    session.add_all([street, other])
    await session.flush()
    return Catalog(species=species, warehouse=warehouse, street=street, other_street=other)


class SleeperFactory(Protocol):
    async def __call__(
        self, *, status: SleeperStatus = ..., location: Location | None = ..., tag: str = ...
    ) -> Sleeper: ...


@pytest.fixture
def make_sleeper(session: AsyncSession, catalog: Catalog) -> SleeperFactory:
    """Dormente direto no banco (sem movimentação), no estado pedido."""

    async def _make(
        *,
        status: SleeperStatus = SleeperStatus.IN_STOCK,
        location: Location | None = None,
        tag: str = "",
    ) -> Sleeper:
        in_yard = status in (SleeperStatus.IN_STOCK, SleeperStatus.QUARANTINE)
        sleeper = Sleeper(
            rfid_tag=tag or f"TAG{uuid.uuid4().hex[:12].upper()}",
            species_id=catalog.species.id,
            status=status,
            current_location_id=(location or catalog.street).id if in_yard else None,
        )
        session.add(sleeper)
        await session.flush()
        return sleeper

    return _make


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP falando com o app em memória, usando a sessão do teste."""
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
