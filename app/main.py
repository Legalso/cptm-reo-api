"""Ponto de entrada: cria o FastAPI com CORS, handlers de erro e routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.openapi import install_openapi
from app.api.routes import (
    auth,
    indicators,
    inspections,
    locations,
    monitoring,
    sleepers,
    species,
    stock,
    sync,
    users,
)
from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.db.engine import engine

DESCRIPTION = """
API do **Projeto REO / CPTM**: rastreio, movimentação, inventário e inspeção digital de
dormentes ferroviários identificados por tag RFID.

* **Autenticação:** `POST /auth/login` (matrícula ou e-mail) → envie o `access_token` em
  `Authorization: Bearer <token>` (botão *Authorize*). Vale 15 min; renove em `POST /auth/refresh`.
* **Erros:** sempre `{"detail": str, "code": str}`; o `code` é estável para o front decidir.
* **Datas:** UTC, ISO 8601. Sem fuso = UTC.
* **Listagens:** `limit` (padrão 50, máx. 200) e `offset`; resposta `{items, total, limit, offset}`.
* **Offline:** registros de campo aceitam `client_uuid`; reenvio não duplica (201 cria, 200 repete).
"""

TAGS = [
    {"name": "Autenticação", "description": "Login, refresh, usuário atual e convite."},
    {"name": "Usuários", "description": "Gestão de usuários e papéis (admin)."},
    {"name": "Espécies", "description": "Catálogo de madeiras (especialista mantém)."},
    {"name": "Locais", "description": "Pátios e ruas (supervisor mantém)."},
    {"name": "Dormentes", "description": "Cadastro, busca por tag RFID e histórico."},
    {"name": "Estoque", "description": "Movimentação, posicionamento, inventário e ocorrências."},
    {"name": "Inspeções", "description": "Checklist digital; reprovação → quarentena."},
    {"name": "Sincronização", "description": "Lote offline do app, idempotente por client_uuid."},
    {"name": "Indicadores e logs", "description": "Dashboard e auditoria (supervisor, admin)."},
    {"name": "Monitoramento", "description": "Saúde da API (sem autenticação)."},
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Fecha o pool de conexões ao desligar."""
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Fábrica do app (usada pelo uvicorn e pelos testes)."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)

    for module in (
        auth,
        users,
        species,
        locations,
        sleepers,
        stock,
        inspections,
        sync,
        indicators,
        monitoring,
    ):
        app.include_router(module.router)
    install_openapi(app)
    return app


app = create_app()
