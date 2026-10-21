"""Catálogo de espécies (mantido pelo especialista)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.species import WoodSpecies
from app.models.user import User
from app.repositories import species as species_repo
from app.schemas.common import PageParams
from app.schemas.species import SpeciesCreate, SpeciesUpdate
from app.services import audit


async def get(session: AsyncSession, species_id: uuid.UUID) -> WoodSpecies:
    species = await species_repo.get_by_id(session, species_id)
    if species is None:
        raise NotFoundError("Espécie não encontrada.", code="species_not_found")
    return species


async def list_species(
    session: AsyncSession, page: PageParams, *, active: bool | None, search: str | None
) -> tuple[list[WoodSpecies], int]:
    return await species_repo.list_species(session, page, active=active, search=search)


async def create(session: AsyncSession, data: SpeciesCreate, actor: User) -> WoodSpecies:
    """Código é único: é ele que aparece na plaqueta e na ficha de papel."""
    if await species_repo.get_by_code(session, data.code):
        raise ConflictError("Código de espécie já existe.", code="species_code_taken")
    species = WoodSpecies(**data.model_dump())
    await audit.create_with_audit(session, species, actor_id=actor.id, entity="wood_species")
    await session.commit()
    return species


async def update(
    session: AsyncSession, species_id: uuid.UUID, data: SpeciesUpdate, actor: User
) -> WoodSpecies:
    species = await get(session, species_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("active") is None:
        changes.pop("active", None)
    scientific = changes.get("scientific_name", species.scientific_name)
    common = changes.get("common_name", species.common_name)
    if not (scientific or common):
        raise UnprocessableError("A espécie precisa de ao menos um nome.")
    if await audit.update_with_audit(
        session, species, changes, actor_id=actor.id, entity="wood_species"
    ):
        await session.commit()
    return species
