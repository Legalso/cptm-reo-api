"""Respostas de erro documentadas no OpenAPI (para o /docs servir de manual)."""

from typing import Any

from app.schemas.common import ErrorResponse

_DESCRIPTIONS = {
    401: "Sem token ou token inválido/expirado",
    403: "Papel sem permissão",
    404: "Recurso não encontrado",
    409: "Conflito ou regra de negócio violada",
    422: "Dados inválidos",
    501: "Ainda não implementado (fase 2)",
}


def errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Monta o dicionário `responses` com o schema de erro padrão."""
    return {code: {"model": ErrorResponse, "description": _DESCRIPTIONS[code]} for code in codes}


# Combinações mais comuns.
AUTH = errors(401, 403)
AUTH_VALIDATION = errors(401, 403, 422)
