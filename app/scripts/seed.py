"""Seed idempotente: espécies da ficha, pátio TG/Rua 08 e usuário admin.

Uso: `uv run python -m app.scripts.seed`. Rodar de novo só cria o que falta;
nada existente é sobrescrito (inclusive a senha do admin).
"""

import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.models.enums import LocationKind, Role
from app.models.location import Location
from app.models.species import WoodSpecies
from app.models.user import User
from app.services import audit

logger = logging.getLogger(__name__)

# (código, nome científico, nome comum) — ficha de dormentes da Rua 08.
SPECIES: list[tuple[str, str | None, str | None]] = [
    ("01", "Apuleia leiocarpa", None),
    ("04", "Bowdichia brasiliensis/nitida", None),
    ("05", "Bowdichia brasiliensis/nitida/Diplotropis purpurea", None),
    ("07", "Dialium guianense", None),
    ("09", "Dipteryx odorata", None),
    ("10", "Dipteryx spp", None),
    ("11", "Enterolobium schomburgkii", None),
    ("12", "Goupia glabra", None),
    ("13", "Hymenaea courbaril", None),
    ("15", "Hymenolobium petraeum", None),
    ("17", "Ocotea neesiana", None),
    ("19", None, "Angelim Vermelho (Promap)"),
    ("20", None, "Coimmal (dormentes antigos)"),
    ("21", None, "Veneer (dormentes antigos)"),
    ("22", "Astronium graveolens/fraxinifolium", None),
]

WAREHOUSE_NAME = "TG – Três Guri"
STREET_NAMES = ["Rua 08"]


@dataclass
class SeedReport:
    """O que foi criado nesta execução."""

    created: list[str] = field(default_factory=list)


async def _seed_species(session: AsyncSession, report: SeedReport) -> None:
    existing = set((await session.scalars(select(WoodSpecies.code))).all())
    for code, scientific, common in SPECIES:
        if code in existing:
            continue
        species = WoodSpecies(code=code, scientific_name=scientific, common_name=common)
        session.add(species)
        await session.flush()
        await audit.record(
            session,
            actor_id=None,
            action="seed",
            entity="wood_species",
            entity_id=species.id,
            after=audit.snapshot(species),
        )
        report.created.append(f"espécie {code}")


async def _get_or_create_location(
    session: AsyncSession,
    report: SeedReport,
    name: str,
    kind: LocationKind,
    parent: Location | None,
) -> Location:
    parent_id = parent.id if parent else None
    same_parent = Location.parent_id == parent_id if parent_id else Location.parent_id.is_(None)
    location = await session.scalar(select(Location).where(Location.name == name, same_parent))
    if location is not None:
        return location
    location = Location(name=name, kind=kind, parent_id=parent_id)
    session.add(location)
    await session.flush()
    await audit.record(
        session,
        actor_id=None,
        action="seed",
        entity="location",
        entity_id=location.id,
        after=audit.snapshot(location),
    )
    report.created.append(f"local {name}")
    return location


async def _seed_admin(session: AsyncSession, settings: Settings, report: SeedReport) -> None:
    email = settings.seed_admin_email
    registration = settings.seed_admin_registration
    password = settings.seed_admin_password
    if not (email and registration and password):
        logger.warning("SEED_ADMIN_* incompleto: admin não criado")
        return
    if password.get_secret_value() == "troque-isto":
        logger.warning("SEED_ADMIN_PASSWORD ainda é o valor de exemplo: admin não criado")
        return
    email, registration = email.strip().lower(), registration.strip().upper()
    found = await session.scalar(
        select(User).where((User.email == email) | (User.registration == registration))
    )
    if found is not None:
        return
    admin = User(
        name=settings.seed_admin_name,
        email=email,
        registration=registration,
        password_hash=hash_password(password.get_secret_value()),
        role=Role.ADMIN,
    )
    session.add(admin)
    await session.flush()
    await audit.record(
        session,
        actor_id=None,
        action="seed",
        entity="user",
        entity_id=admin.id,
        after=audit.snapshot(admin),
    )
    report.created.append(f"admin {email}")


async def run_seed(session: AsyncSession, settings: Settings) -> SeedReport:
    """Executa todas as etapas do seed numa única transação."""
    report = SeedReport()
    await _seed_species(session, report)
    warehouse = await _get_or_create_location(
        session, report, WAREHOUSE_NAME, LocationKind.WAREHOUSE, None
    )
    for street in STREET_NAMES:
        await _get_or_create_location(session, report, street, LocationKind.STREET, warehouse)
    await _seed_admin(session, settings, report)
    await session.commit()
    return report


async def main() -> None:
    """Entrada do script de linha de comando."""
    from app.db.engine import SessionFactory, engine

    settings = get_settings()
    configure_logging(settings.log_level)
    async with SessionFactory() as session:
        report = await run_seed(session, settings)
    await engine.dispose()
    if report.created:
        logger.info("Seed criou: %s", ", ".join(report.created))
    else:
        logger.info("Seed: nada a criar, banco já está populado")


if __name__ == "__main__":
    asyncio.run(main())
