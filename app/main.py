"""Ponto de entrada: cria o FastAPI com CORS, handlers de erro e routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, monitoring, users
from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.db.engine import engine

DESCRIPTION = """
API do **Projeto REO / CPTM**: rastreio, movimentação, inventário e inspeção digital de
dormentes ferroviários identificados por tag RFID.

* Autenticação: `POST /auth/login` → use o `access_token` como `Authorization: Bearer <token>`.
* Erros sempre no formato `{"detail": str, "code": str}`.
* Datas em UTC (ISO 8601). Listagens paginadas com `limit`/`offset`.
"""


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

    for module in (auth, users, monitoring):
        app.include_router(module.router)
    return app


app = create_app()
