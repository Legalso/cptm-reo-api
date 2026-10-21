"""Ajustes no OpenAPI gerado para o /docs refletir a API de verdade."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.schemas.common import ErrorResponse, ValidationErrorResponse

_VALIDATION_REF = "#/components/schemas/ValidationErrorResponse"


def _validation_response() -> dict[str, Any]:
    return {
        "description": "Dados inválidos",
        "content": {"application/json": {"schema": {"$ref": _VALIDATION_REF}}},
    }


def install_openapi(app: FastAPI) -> None:
    """Troca o 422 padrão do FastAPI (`HTTPValidationError`) pelo nosso formato."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (ErrorResponse, ValidationErrorResponse):
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            for name, sub in definition.pop("$defs", {}).items():
                components.setdefault(name, sub)
            components[model.__name__] = definition
        components.pop("HTTPValidationError", None)
        components.pop("ValidationError", None)
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                responses = operation.get("responses", {})
                if "422" in responses:
                    responses["422"] = _validation_response()
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
