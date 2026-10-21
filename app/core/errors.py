"""Exceções de domínio e handlers que garantem o formato único `{detail, code}`."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Erro base da API; subclasses definem status HTTP e `code` padrão."""

    status_code = 400
    code = "bad_request"
    default_detail = "Requisição inválida."

    def __init__(self, detail: str | None = None, code: str | None = None) -> None:
        self.detail = detail or self.default_detail
        if code:
            self.code = code
        super().__init__(self.detail)


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    default_detail = "Credenciais ausentes ou inválidas."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    default_detail = "Seu papel não permite esta ação."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    default_detail = "Recurso não encontrado."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    default_detail = "Conflito com o estado atual do recurso."


class BusinessRuleError(AppError):
    """Violação de regra de negócio (ex.: movimentar dormente descartado)."""

    status_code = 409
    code = "business_rule"
    default_detail = "Operação não permitida pelas regras de negócio."


class FeatureNotImplementedError(AppError):
    """Funcionalidade prevista para fase futura (stub)."""

    status_code = 501
    code = "not_implemented"
    default_detail = "Funcionalidade ainda não implementada."


HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "too_many_requests",
}


def error_body(detail: str, code: str, **extra: Any) -> dict[str, Any]:
    """Monta o corpo de erro padrão."""
    return {"detail": detail, "code": code, **extra}


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(error_body(exc.detail, exc.code), exc.status_code, headers=headers)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = HTTP_CODES.get(exc.status_code, f"http_{exc.status_code}")
    return JSONResponse(error_body(str(exc.detail), code), exc.status_code, headers=exc.headers)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """422 com resumo legível em `detail` e a lista completa em `errors`."""
    assert isinstance(exc, RequestValidationError)
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    first = errors[0] if errors else {"loc": [], "msg": "inválido"}
    field = ".".join(str(p) for p in first["loc"] if p != "body") or "corpo"
    detail = f"Dados inválidos em '{field}': {first['msg']}"
    return JSONResponse(error_body(detail, "validation_error", errors=errors), 422)


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro não tratado", exc_info=exc)
    return JSONResponse(error_body("Erro interno do servidor.", "internal_error"), 500)


def register_error_handlers(app: FastAPI) -> None:
    """Liga todos os handlers no app para que nenhum erro fuja do formato padrão."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
