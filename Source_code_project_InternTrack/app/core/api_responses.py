import json
import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


logger = logging.getLogger(__name__)
_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_RESPONSE_HEADERS_TO_REBUILD = {
    "content-length",
    "content-type",
    "content-encoding",
    "transfer-encoding",
}


def _failure(
    message: str,
    errors: list[dict[str, str | None]],
) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "data": None,
        "errors": errors,
    }


def _error_item(field: str | None, message: str) -> dict[str, str | None]:
    return {"field": field, "message": message}


def _openapi_error_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["success", "message", "data", "errors"],
        "properties": {
            "success": {"type": "boolean", "const": False},
            "message": {"type": "string"},
            "data": {"type": "null"},
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["field", "message"],
                    "properties": {
                        "field": {"type": ["string", "null"]},
                        "message": {"type": "string"},
                    },
                },
            },
        },
    }


def _success_openapi_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["success", "message", "data", "errors"],
        "properties": {
            "success": {"type": "boolean", "const": True},
            "message": {"type": "string"},
            "data": data_schema,
            "errors": {"type": "null"},
        },
    }


class JsonEnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if (
            response.status_code < 200
            or response.status_code >= 300
            or response.status_code == 204
            or content_type != "application/json"
            or request.url.path in {request.app.openapi_url, request.app.docs_url, request.app.redoc_url}
        ):
            return response

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
        body = b"".join(chunks)
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error("A successful API response was not valid JSON.")
            return Response(
                content=body,
                status_code=response.status_code,
                headers=_preserved_headers(response),
                media_type=content_type,
                background=response.background,
            )

        headers = _preserved_headers(response)
        if isinstance(data, dict) and {
            "success",
            "message",
            "data",
            "errors",
        }.issubset(data):
            return JSONResponse(
                content=data,
                status_code=response.status_code,
                headers=headers,
                background=response.background,
            )

        return JSONResponse(
            content={
                "success": True,
                "message": "Request successful",
                "data": data,
                "errors": None,
            },
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )


def _preserved_headers(response: Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in _RESPONSE_HEADERS_TO_REBUILD
    }


async def _http_exception_handler(
    _request: Request,
    exception: StarletteHTTPException,
) -> JSONResponse:
    if isinstance(exception.detail, str):
        message = exception.detail
    else:
        message = "The request could not be completed."
    return JSONResponse(
        content=_failure(message, [_error_item(None, message)]),
        status_code=exception.status_code,
        headers=exception.headers,
    )


async def _validation_exception_handler(
    _request: Request,
    exception: RequestValidationError,
) -> JSONResponse:
    errors: list[dict[str, str | None]] = []
    for error in exception.errors():
        location = error.get("loc", ())
        field_parts = [
            str(part)
            for part in location
            if part not in {"body", "query", "path", "header", "cookie"}
        ]
        field = ".".join(field_parts) or "request"
        message = str(error.get("msg", "Invalid value."))
        errors.append(_error_item(field, message))

    return JSONResponse(
        content=_failure("Validation failed", errors),
        status_code=422,
    )


async def _sqlalchemy_exception_handler(
    _request: Request,
    exception: SQLAlchemyError,
) -> JSONResponse:
    logger.error(
        "Unhandled database exception.",
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    message = "A database error occurred."
    return JSONResponse(
        content=_failure(message, [_error_item(None, message)]),
        status_code=500,
    )


async def _unhandled_exception_handler(
    _request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled backend exception.",
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    message = "An unexpected error occurred."
    return JSONResponse(
        content=_failure(message, [_error_item(None, message)]),
        status_code=500,
    )


def install_api_response_handling(app: FastAPI) -> None:
    app.add_middleware(JsonEnvelopeMiddleware)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, _sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    original_openapi = app.openapi

    def openapi_with_envelopes() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        openapi_schema = original_openapi()
        for path_item in openapi_schema.get("paths", {}).values():
            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS or not isinstance(operation, Mapping):
                    continue
                responses = operation.get("responses", {})
                has_json_success = False
                for response_code, response_schema in responses.items():
                    if not isinstance(response_schema, dict):
                        continue
                    content = response_schema.get("content", {})
                    json_response = content.get("application/json")
                    if json_response is None:
                        continue
                    if response_code.isdigit() and 200 <= int(response_code) < 300:
                        if response_code == "204":
                            continue
                        raw_data_schema = json_response.get("schema", {})
                        json_response["schema"] = _success_openapi_schema(raw_data_schema)
                        has_json_success = True
                    elif response_code == "default" or (
                        response_code.isdigit() and int(response_code) >= 400
                    ):
                        json_response["schema"] = _openapi_error_schema()

                if has_json_success:
                    responses.setdefault(
                        "default",
                        {
                            "description": "Standard API error response.",
                            "content": {
                                "application/json": {
                                    "schema": _openapi_error_schema()
                                }
                            },
                        },
                    )

        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = openapi_with_envelopes
