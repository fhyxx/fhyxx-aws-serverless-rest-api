"""API Gateway HTTP API v2 router and response formatting."""

import json
import logging
from typing import Any

from task_api.errors import ApiError
from task_api.repository import TaskRepository
from task_api.service import TaskService
from task_api.validation import (
    decode_cursor,
    encode_cursor,
    parse_body,
    parse_page_size,
    validate_create,
    validate_patch,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def response(status: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8", "cache-control": "no-store"},
        "body": ""
        if status == 204
        else json.dumps(payload if payload is not None else {}, separators=(",", ":")),
    }


def _user_id(event: dict[str, Any]) -> str:
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        user_id = claims["sub"]
    except (KeyError, TypeError) as exc:
        raise ApiError(401, "unauthorized", "A valid authenticated user is required.") from exc
    if not isinstance(user_id, str) or not user_id:
        raise ApiError(401, "unauthorized", "A valid authenticated user is required.")
    return user_id


def _service() -> TaskService:
    return TaskService(TaskRepository.from_environment())


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    """Return API fields only; keep DynamoDB key material internal."""
    fields = ("id", "title", "description", "status", "due_date", "created_at", "updated_at")
    return {field: task[field] for field in fields if field in task}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    del context
    try:
        user_id = _user_id(event)
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        path = event.get("rawPath", "")
        route_params = event.get("pathParameters") or {}
        service = _service()

        if method == "POST" and path == "/tasks":
            task = service.create(user_id, validate_create(parse_body(event)))
            return response(201, {"task": _task_view(task)})
        if method == "GET" and path == "/tasks":
            query = event.get("queryStringParameters") or {}
            result = service.list(
                user_id,
                parse_page_size(query.get("limit")),
                decode_cursor(query.get("cursor"), user_id),
            )
            return response(
                200,
                {
                    "items": [_task_view(item) for item in result["items"]],
                    "next_cursor": encode_cursor(result["next_cursor"]),
                },
            )
        task_id = route_params.get("id")
        if method == "GET" and task_id:
            return response(200, {"task": _task_view(service.get(user_id, task_id))})
        if method == "PATCH" and task_id:
            task = service.update(user_id, task_id, validate_patch(parse_body(event)))
            return response(200, {"task": _task_view(task)})
        if method == "DELETE" and task_id:
            service.delete(user_id, task_id)
            return response(204)
        raise ApiError(404, "route_not_found", "Route not found.")
    except ApiError as exc:
        return response(exc.status_code, {"error": {"code": exc.code, "message": exc.message}})
    except Exception:
        logger.exception("Unhandled API error", extra={"request_id": _request_id(event)})
        return response(
            500, {"error": {"code": "internal_error", "message": "An internal error occurred."}}
        )


def _request_id(event: dict[str, Any]) -> str | None:
    try:
        return event["requestContext"]["requestId"]
    except (KeyError, TypeError):
        return None
