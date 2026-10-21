"""Consultas do catálogo de espécies."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.species import WoodSpecies
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_id(session: AsyncSession, species_id: uuid.UUID) -> WoodSpecies | None:
    return await session.get(WoodSpecies, species_id)


async def get_by_code(session: AsyncSession, code: str) -> WoodSpecies | None:
    return await session.scalar(select(WoodSpecies).where(WoodSpecies.code == code))


async def list_species(
    session: AsyncSession, page: PageParams, *, active: bool | None, search: str | None
) -> tuple[list[WoodSpecies], int]:
    stmt = select(WoodSpecies).order_by(WoodSpecies.code)
    if active is not None:
        stmt = stmt.where(WoodSpecies.active == active)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                WoodSpecies.code.ilike(pattern),
                WoodSpecies.scientific_name.ilike(pattern),
                WoodSpecies.common_name.ilike(pattern),
            )
        )
    return await paginate(session, stmt, page)
