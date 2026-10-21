"""Helpers genéricos de consulta."""

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import PageParams


async def paginate[T](
    session: AsyncSession, stmt: Select[T], page: PageParams
) -> tuple[list[T], int]:
    """Executa a consulta paginada e o total (sem a ordenação, que só custa)."""
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = await session.scalar(count_stmt) or 0
    rows = await session.scalars(stmt.limit(page.limit).offset(page.offset))
    return list(rows.unique().all()), total
