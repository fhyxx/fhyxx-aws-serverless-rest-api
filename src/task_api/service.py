"""Task use cases independent of HTTP and DynamoDB transport details."""

import uuid
from typing import Any

from task_api.errors import NotFoundError
from task_api.repository import TaskRepository


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def create(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self.repository.create(user_id, {"id": str(uuid.uuid4()), **fields})

    def list(self, user_id: str, limit: int, cursor: dict[str, Any] | None) -> dict[str, Any]:
        result = self.repository.list(user_id, limit, cursor)
        return {"items": result["items"], "next_cursor": result["last_key"]}

    def get(self, user_id: str, task_id: str) -> dict[str, Any]:
        item = self.repository.get(user_id, task_id)
        if item is None:
            raise NotFoundError()
        return item

    def update(self, user_id: str, task_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        item = self.repository.update(user_id, task_id, fields)
        if item is None:
            raise NotFoundError()
        return item

    def delete(self, user_id: str, task_id: str) -> None:
        if not self.repository.delete(user_id, task_id):
            raise NotFoundError()
