from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.location import Location
from app.models.species import WoodSpecies
from app.models.user import User
from app.scripts.seed import SPECIES, run_seed


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    settings = get_settings().model_copy(
        update={
            "seed_admin_email": "Seed.Admin@REO.local",
            "seed_admin_registration": "adm-9",
            "seed_admin_password": SecretStr("Senha-forte-1"),
        }
    )

    first = await run_seed(session, settings)
    second = await run_seed(session, settings)

    assert len(first.created) == len(SPECIES) + 2 + 1
    assert second.created == []
    assert await session.scalar(select(func.count()).select_from(WoodSpecies)) == len(SPECIES)
    street = await session.scalar(select(Location).where(Location.name == "Rua 08"))
    assert street is not None and street.parent_id is not None
    admin = await session.scalar(select(User).where(User.email == "seed.admin@reo.local"))
    assert admin is not None
    assert admin.registration == "ADM-9"
    assert verify_password("Senha-forte-1", admin.password_hash)


async def test_seed_skips_admin_with_example_password(session: AsyncSession) -> None:
    settings = get_settings().model_copy(
        update={
            "seed_admin_email": "x@reo.local",
            "seed_admin_registration": "X-1",
            "seed_admin_password": SecretStr("troque-isto"),
        }
    )
    report = await run_seed(session, settings)
    assert not any(item.startswith("admin") for item in report.created)
