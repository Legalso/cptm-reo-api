"""Seed idempotente: espécies da ficha, pátios com suas ruas e usuário admin.

Uso: `uv run python -m app.scripts.seed`. Rodar de novo só cria o que falta;
nada existente é sobrescrito (inclusive a senha do admin). Exceções: o nome legado do
pátio principal é renomeado uma vez (ver `LEGACY_YARD_NAMES`), e o nome popular vazio de
uma espécie já cadastrada é completado (um nome popular preenchido nunca é trocado).
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

# (código, nome científico, nome popular) — ficha de dormentes da Rua 08.
# Nomes populares conferidos em catálogos de madeiras (IPT/USP, LPF/SFB, OIMT e a lista de
# nomes vulgares de MT). Um mesmo nome popular pode valer para várias espécies, e vice-versa.
SPECIES: list[tuple[str, str | None, str | None]] = [
    ("01", "Apuleia leiocarpa", "Garapa"),
    ("04", "Bowdichia brasiliensis/nitida", "Sucupira"),
    ("05", "Bowdichia brasiliensis/nitida/Diplotropis purpurea", "Sucupira"),
    ("07", "Dialium guianense", "Jutaí-pororoca"),
    ("09", "Dipteryx odorata", "Cumaru"),
    ("10", "Dipteryx spp", "Cumaru"),
    ("11", "Enterolobium schomburgkii", "Orelha-de-macaco"),
    ("12", "Goupia glabra", "Cupiúba"),
    ("13", "Hymenaea courbaril", "Jatobá"),
    ("15", "Hymenolobium petraeum", "Angelim-pedra"),
    # TODO(decidir): nome popular de Ocotea neesiana não encontrado em fonte confiável
    # ("canela" vale para dezenas de Ocotea); confirmar com o especialista.
    ("17", "Ocotea neesiana", None),
    ("19", None, "Angelim Vermelho (Promap)"),
    ("20", None, "Coimmal (dormentes antigos)"),
    ("21", None, "Veneer (dormentes antigos)"),
    ("22", "Astronium graveolens/fraxinifolium", "Guaritá / Gonçalo-alves"),
]

MAIN_YARD = "Pátio Av. Raimundo Pereira de Magalhães, 200"
# Pátio → ruas. O primeiro é o principal (onde está a ficha da Rua 08).
YARDS: dict[str, list[str]] = {
    MAIN_YARD: ["Rua 08"],
    "Pátio Presidente Altino": ["Rua 01", "Rua 02"],
}
# Nome antigo → nome atual. "TG – Três Guri" veio da ficha de papel e não foi confirmado;
# em 2026-11-26 o time definiu o pátio principal pelo endereço. Bancos criados antes
# têm o nome antigo: o seed renomeia (com auditoria) em vez de criar um pátio duplicado.
LEGACY_YARD_NAMES: dict[str, str] = {"TG – Três Guri": MAIN_YARD}


@dataclass
class SeedReport:
    """O que foi criado nesta execução."""

    created: list[str] = field(default_factory=list)


async def _fill_common_name(
    session: AsyncSession, report: SeedReport, species: WoodSpecies, common: str
) -> None:
    """Completa o nome popular vazio de uma espécie já cadastrada (nunca troca um preenchido)."""
    before = audit.snapshot(species)
    species.common_name = common
    await session.flush()
    await audit.record(
        session,
        actor_id=None,
        action="seed_fill",
        entity="wood_species",
        entity_id=species.id,
        before=before,
        after=audit.snapshot(species),
    )
    report.created.append(f"nome popular da espécie {species.code}")


async def _seed_species(session: AsyncSession, report: SeedReport) -> None:
    existing = {s.code: s for s in (await session.scalars(select(WoodSpecies))).all()}
    for code, scientific, common in SPECIES:
        if code in existing:
            if common and existing[code].common_name is None:
                await _fill_common_name(session, report, existing[code], common)
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


async def _rename_legacy_yards(session: AsyncSession, report: SeedReport) -> None:
    """Renomeia pátios com nome legado, se o nome atual ainda não existir."""
    for old, new in LEGACY_YARD_NAMES.items():
        top_level = Location.parent_id.is_(None)
        legacy = await session.scalar(select(Location).where(Location.name == old, top_level))
        current = await session.scalar(select(Location).where(Location.name == new, top_level))
        if legacy is None or current is not None:
            continue
        before = audit.snapshot(legacy)
        legacy.name = new
        await session.flush()
        await audit.record(
            session,
            actor_id=None,
            action="seed_rename",
            entity="location",
            entity_id=legacy.id,
            before=before,
            after=audit.snapshot(legacy),
        )
        report.created.append(f"local {old} renomeado para {new}")


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
    await _rename_legacy_yards(session, report)
    for yard_name, streets in YARDS.items():
        yard = await _get_or_create_location(
            session, report, yard_name, LocationKind.WAREHOUSE, None
        )
        for street in streets:
            await _get_or_create_location(session, report, street, LocationKind.STREET, yard)
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
