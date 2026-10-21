"""Consultas de locais."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LocationKind
from app.models.location import Location
from app.repositories.base import paginate
from app.schemas.common import PageParams


async def get_by_id(session: AsyncSession, location_id: uuid.UUID) -> Location | None:
    return await session.get(Location, location_id)


async def get_sibling_by_name(
    session: AsyncSession, parent_id: uuid.UUID | None, name: str
) -> Location | None:
    same_parent = Location.parent_id == parent_id if parent_id else Location.parent_id.is_(None)
    return await session.scalar(select(Location).where(same_parent, Location.name == name))


async def list_locations(
    session: AsyncSession,
    page: PageParams,
    *,
    kind: LocationKind | None,
    parent_id: uuid.UUID | None,
    active: bool | None,
    search: str | None,
) -> tuple[list[Location], int]:
    stmt = select(Location).order_by(Location.kind.desc(), Location.name)
    if kind is not None:
        stmt = stmt.where(Location.kind == kind)
    if parent_id is not None:
        stmt = stmt.where(Location.parent_id == parent_id)
    if active is not None:
        stmt = stmt.where(Location.active == active)
    if search:
        stmt = stmt.where(Location.name.ilike(f"%{search}%"))
    return await paginate(session, stmt, page)
