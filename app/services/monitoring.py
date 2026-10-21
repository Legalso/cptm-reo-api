"""Montagem do status de saúde da API."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_VERSION, get_settings
from app.repositories.monitoring import ping_database
from app.schemas.monitoring import MonitoringStatus


async def get_status(session: AsyncSession) -> MonitoringStatus:
    """Agrega versão, ambiente e conectividade do banco num único retrato."""
    db_ok = await ping_database(session)
    return MonitoringStatus(
        status="ok" if db_ok else "degraded",
        version=APP_VERSION,
        environment=get_settings().app_env,
        database="ok" if db_ok else "unavailable",
        # TODO(decidir): provedor de e-mail de convite ainda não definido.
        email_configured=False,
        server_time=datetime.now(UTC),
    )
