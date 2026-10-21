"""Locais: pátio (warehouse) → rua (street)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, UnprocessableError
from app.models.enums import LocationKind
from app.models.location import Location
from app.models.user import User
from app.repositories import locations as location_repo
from app.schemas.common import PageParams
from app.schemas.location import LocationCreate, LocationUpdate
from app.services import audit


async def get(session: AsyncSession, location_id: uuid.UUID) -> Location:
    location = await location_repo.get_by_id(session, location_id)
    if location is None:
        raise NotFoundError("Local não encontrado.", code="location_not_found")
    return location


async def get_active(session: AsyncSession, location_id: uuid.UUID) -> Location:
    """Local que pode receber dormentes: precisa existir e estar ativo."""
    location = await get(session, location_id)
    if not location.active:
        raise BusinessRuleError("Local está inativo.", code="location_inactive")
    return location


async def list_locations(
    session: AsyncSession,
    page: PageParams,
    *,
    kind: LocationKind | None,
    parent_id: uuid.UUID | None,
    active: bool | None,
    search: str | None,
) -> tuple[list[Location], int]:
    return await location_repo.list_locations(
        session, page, kind=kind, parent_id=parent_id, active=active, search=search
    )


async def _validate_hierarchy(session: AsyncSession, data: LocationCreate) -> None:
    """Rua fica dentro de um pátio; pátio fica na raiz."""
    if data.kind == LocationKind.WAREHOUSE:
        if data.parent_id is not None:
            raise UnprocessableError("Pátio/armazém não pode ter local pai.")
        return
    if data.parent_id is None:
        raise UnprocessableError("Rua precisa de parent_id (pátio).")
    parent = await get(session, data.parent_id)
    if parent.kind != LocationKind.WAREHOUSE:
        raise UnprocessableError("O pai de uma rua deve ser um pátio/armazém.")


async def _ensure_unique_name(
    session: AsyncSession, parent_id: uuid.UUID | None, name: str, current: Location | None = None
) -> None:
    found = await location_repo.get_sibling_by_name(session, parent_id, name)
    if found is not None and found is not current:
        raise ConflictError("Já existe local com esse nome aqui.", code="location_name_taken")


async def create(session: AsyncSession, data: LocationCreate, actor: User) -> Location:
    name = data.name.strip()
    await _validate_hierarchy(session, data)
    await _ensure_unique_name(session, data.parent_id, name)
    location = Location(**{**data.model_dump(), "name": name})
    await audit.create_with_audit(session, location, actor_id=actor.id, entity="location")
    await session.commit()
    return location


async def update(
    session: AsyncSession, location_id: uuid.UUID, data: LocationUpdate, actor: User
) -> Location:
    location = await get(session, location_id)
    changes = data.model_dump(exclude_unset=True)
    for key in ("name", "active"):
        if key in changes and changes[key] is None:
            changes.pop(key)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        await _ensure_unique_name(session, location.parent_id, changes["name"], location)
    if await audit.update_with_audit(
        session, location, changes, actor_id=actor.id, entity="location"
    ):
        await session.commit()
    return location
