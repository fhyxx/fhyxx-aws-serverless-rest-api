"""Request body and pagination validation."""

import base64
import binascii
import json
from datetime import date
from typing import Any

from task_api.errors import ApiError

MAX_BODY_BYTES = 16_384
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5_000
MAX_PAGE_SIZE = 100


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if not isinstance(body, str):
        raise ApiError(400, "invalid_body", "A JSON object request body is required.")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "payload_too_large", "Request body exceeds 16 KB.")
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ApiError(400, "invalid_json", "Request body must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ApiError(400, "invalid_body", "Request body must be a JSON object.")
    return value


def validate_create(body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "description", "status", "due_date"}
    unexpected = set(body) - allowed
    if unexpected:
        raise ApiError(
            400, "unknown_fields", f"Unsupported field(s): {', '.join(sorted(unexpected))}."
        )
    title = _text(body.get("title"), "title", MAX_TITLE_LENGTH, required=True)
    description = _text(body.get("description", ""), "description", MAX_DESCRIPTION_LENGTH)
    status = body.get("status", "open")
    if not isinstance(status, str) or status not in {"open", "in_progress", "completed"}:
        raise ApiError(400, "invalid_status", "status must be open, in_progress, or completed.")
    due_date = _date(body.get("due_date", ""))
    return {"title": title, "description": description, "status": status, "due_date": due_date}


def validate_patch(body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "description", "status", "due_date"}
    if not body:
        raise ApiError(400, "empty_patch", "At least one task field must be provided.")
    unexpected = set(body) - allowed
    if unexpected:
        raise ApiError(
            400, "unknown_fields", f"Unsupported field(s): {', '.join(sorted(unexpected))}."
        )
    result: dict[str, Any] = {}
    if "title" in body:
        result["title"] = _text(body["title"], "title", MAX_TITLE_LENGTH, required=True)
    if "description" in body:
        result["description"] = _text(body["description"], "description", MAX_DESCRIPTION_LENGTH)
    if "status" in body:
        status = body["status"]
        if not isinstance(status, str) or status not in {"open", "in_progress", "completed"}:
            raise ApiError(400, "invalid_status", "status must be open, in_progress, or completed.")
        result["status"] = status
    if "due_date" in body:
        result["due_date"] = _date(body["due_date"])
    return result


def parse_page_size(value: str | None) -> int:
    if value is None:
        return 20
    try:
        size = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "invalid_limit", "limit must be an integer from 1 to 100.") from exc
    if not 1 <= size <= MAX_PAGE_SIZE:
        raise ApiError(400, "invalid_limit", "limit must be an integer from 1 to 100.")
    return size


def encode_cursor(key: dict[str, Any] | None) -> str | None:
    if key is None:
        return None
    data = json.dumps(key, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def decode_cursor(value: str | None, user_id: str) -> dict[str, Any] | None:
    if not value:
        return None
    if len(value) > 2_048:
        raise ApiError(400, "invalid_cursor", "Pagination cursor is invalid.")
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
    except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise ApiError(400, "invalid_cursor", "Pagination cursor is invalid.") from exc
    if not isinstance(decoded, dict) or set(decoded) != {"PK", "SK"}:
        raise ApiError(400, "invalid_cursor", "Pagination cursor is invalid.")
    if not all(isinstance(decoded[field], str) for field in ("PK", "SK")):
        raise ApiError(400, "invalid_cursor", "Pagination cursor is invalid.")
    if decoded["PK"] != f"USER#{user_id}" or not decoded["SK"].startswith("TASK#"):
        raise ApiError(400, "invalid_cursor", "Pagination cursor is invalid.")
    return decoded


def _text(value: Any, field: str, max_length: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "invalid_field", f"{field} must be a string.")
    cleaned = value.strip()
    if required and not cleaned:
        raise ApiError(400, "invalid_field", f"{field} is required and cannot be blank.")
    if len(cleaned) > max_length:
        raise ApiError(400, "invalid_field", f"{field} exceeds {max_length} characters.")
    return cleaned


def _date(value: Any) -> str:
    date_text = _text(value, "due_date", 10)
    if date_text:
        try:
            parsed = date.fromisoformat(date_text)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_due_date", "due_date must be a real date in YYYY-MM-DD format."
            ) from exc
        if parsed.isoformat() != date_text:
            raise ApiError(
                400, "invalid_due_date", "due_date must be a real date in YYYY-MM-DD format."
            )
    return date_text
