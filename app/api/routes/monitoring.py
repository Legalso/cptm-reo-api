"""Health check público (sem autenticação, conforme contrato do site)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.schemas.monitoring import MonitoringStatus
from app.services import monitoring as monitoring_service

router = APIRouter(prefix="/monitoramento", tags=["Monitoramento"])


@router.get(
    "/status",
    response_model=MonitoringStatus,
    summary="Saúde da API e do banco",
    responses={503: {"model": MonitoringStatus, "description": "Banco indisponível"}},
)
async def get_status(session: SessionDep) -> JSONResponse:
    """Devolve 200 quando tudo responde e 503 (mesmo corpo) quando o banco cai."""
    status = await monitoring_service.get_status(session)
    code = 200 if status.status == "ok" else 503
    return JSONResponse(status.model_dump(mode="json"), status_code=code)
