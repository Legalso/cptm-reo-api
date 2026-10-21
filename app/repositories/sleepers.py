"""Consultas de dormentes."""

import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.enums import SleeperStatus
from app.models.location import Location
from app.models.sleeper import Sleeper
from app.repositories.base import paginate
from app.schemas.common import PageParams


def _with_relations(stmt: Select[Sleeper]) -> Select[Sleeper]:
    return stmt.options(joinedload(Sleeper.species), joinedload(Sleeper.current_location))


async def get_by_id(session: AsyncSession, sleeper_id: uuid.UUID) -> Sleeper | None:
    """Carrega com espécie e local (populate_existing: reflete o que acabou de mudar)."""
    stmt = _with_relations(select(Sleeper).where(Sleeper.id == sleeper_id))
    return await session.scalar(stmt.execution_options(populate_existing=True))


async def get_by_tag(session: AsyncSession, rfid_tag: str) -> Sleeper | None:
    """Busca pela tag (índice único) — caminho mais quente da API."""
    stmt = _with_relations(select(Sleeper).where(Sleeper.rfid_tag == rfid_tag))
    return await session.scalar(stmt.execution_options(populate_existing=True))


async def get_by_tag_for_update(session: AsyncSession, rfid_tag: str) -> Sleeper | None:
    """Mesma busca, travando a linha: evita duas movimentações simultâneas do mesmo dormente."""
    return await session.scalar(
        select(Sleeper).where(Sleeper.rfid_tag == rfid_tag).with_for_update()
    )


async def get_for_update(session: AsyncSession, sleeper_id: uuid.UUID) -> Sleeper | None:
    return await session.scalar(select(Sleeper).where(Sleeper.id == sleeper_id).with_for_update())


async def tag_exists(session: AsyncSession, rfid_tag: str) -> bool:
    found = await session.scalar(select(Sleeper.id).where(Sleeper.rfid_tag == rfid_tag))
    return found is not None


async def list_sleepers(
    session: AsyncSession,
    page: PageParams,
    *,
    status: SleeperStatus | None,
    species_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    search: str | None,
) -> tuple[list[Sleeper], int]:
    stmt = _with_relations(select(Sleeper)).order_by(Sleeper.created_at.desc(), Sleeper.id)
    if status is not None:
        stmt = stmt.where(Sleeper.status == status)
    if species_id is not None:
        stmt = stmt.where(Sleeper.species_id == species_id)
    if location_id is not None:
        # Filtrar por pátio inclui as ruas dele.
        subtree = select(Location.id).where(
            or_(Location.id == location_id, Location.parent_id == location_id)
        )
        stmt = stmt.where(Sleeper.current_location_id.in_(subtree))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Sleeper.registration_record.ilike(pattern), Sleeper.rfid_tag.ilike(pattern))
        )
    return await paginate(session, stmt, page)
