from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.audit_log import AuditLog
from app.models.enums import LocationKind
from app.models.location import Location
from app.models.species import WoodSpecies
from app.models.user import User
from app.scripts.seed import MAIN_YARD, SPECIES, YARDS, run_seed

LOCATIONS_CREATED = len(YARDS) + sum(len(streets) for streets in YARDS.values())


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

    assert len(first.created) == len(SPECIES) + LOCATIONS_CREATED + 1
    assert second.created == []
    assert await session.scalar(select(func.count()).select_from(WoodSpecies)) == len(SPECIES)
    yards = (
        await session.scalars(select(Location.name).where(Location.kind == LocationKind.WAREHOUSE))
    ).all()
    assert sorted(yards) == sorted(YARDS)
    street = await session.scalar(select(Location).where(Location.name == "Rua 08"))
    main = await session.scalar(select(Location).where(Location.name == MAIN_YARD))
    assert street is not None and main is not None and street.parent_id == main.id
    jatoba = await session.scalar(select(WoodSpecies).where(WoodSpecies.code == "13"))
    assert jatoba is not None and jatoba.common_name == "Jatobá"
    admin = await session.scalar(select(User).where(User.email == "seed.admin@reo.local"))
    assert admin is not None
    assert admin.registration == "ADM-9"
    assert verify_password("Senha-forte-1", admin.password_hash)


async def test_seed_renames_legacy_yard_instead_of_duplicating(session: AsyncSession) -> None:
    """Banco antigo com "TG – Três Guri": vira o pátio principal, com as ruas e auditoria."""
    legacy = Location(name="TG – Três Guri", kind=LocationKind.WAREHOUSE)
    session.add(legacy)
    await session.flush()
    session.add(Location(name="Rua 08", kind=LocationKind.STREET, parent_id=legacy.id))
    await session.flush()

    first = await run_seed(session, get_settings())
    second = await run_seed(session, get_settings())

    assert any("renomeado" in item for item in first.created)
    assert second.created == []
    await session.refresh(legacy)
    assert legacy.name == MAIN_YARD
    mains = await session.scalar(
        select(func.count()).select_from(Location).where(Location.name == MAIN_YARD)
    )
    assert mains == 1
    rua_08 = (await session.scalars(select(Location).where(Location.name == "Rua 08"))).all()
    assert [r.parent_id for r in rua_08] == [legacy.id]
    log = await session.scalar(
        select(AuditLog).where(AuditLog.action == "seed_rename", AuditLog.entity_id == legacy.id)
    )
    assert log is not None
    assert log.before is not None and log.before["name"] == "TG – Três Guri"


async def test_seed_fills_only_empty_common_names(session: AsyncSession) -> None:
    """Banco antigo: completa nome popular vazio, com auditoria, sem trocar o já preenchido."""
    empty = WoodSpecies(code="01", scientific_name="Apuleia leiocarpa")
    edited = WoodSpecies(
        code="13", scientific_name="Hymenaea courbaril", common_name="Jatobá-mirim"
    )
    session.add_all([empty, edited])
    await session.flush()

    first = await run_seed(session, get_settings())
    second = await run_seed(session, get_settings())

    await session.refresh(empty)
    await session.refresh(edited)
    assert empty.common_name == "Garapa"
    assert edited.common_name == "Jatobá-mirim"
    assert "nome popular da espécie 01" in first.created
    assert not any("espécie 13" in item for item in first.created)
    assert second.created == []
    log = await session.scalar(
        select(AuditLog).where(AuditLog.action == "seed_fill", AuditLog.entity_id == empty.id)
    )
    assert log is not None and log.before is not None and log.before["common_name"] is None


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
