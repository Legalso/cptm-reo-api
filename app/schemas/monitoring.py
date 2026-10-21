"""Schemas do health check."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MonitoringStatus(BaseModel):
    """Saúde da API: usado pelo site e por probes do provedor de hospedagem."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "version": "0.1.0",
                "environment": "dev",
                "database": "ok",
                "email_configured": False,
                "server_time": "2026-10-21T22:00:00Z",
            }
        }
    )

    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unavailable"]
    email_configured: bool
    server_time: datetime
