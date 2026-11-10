"""DynamoDB single-table repository."""

import os
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


class TaskRepository:
    def __init__(self, table: Any) -> None:
        self.table = table

    @classmethod
    def from_environment(cls) -> "TaskRepository":
        table_name = os.environ.get("TASKS_TABLE")
        if not table_name:
            raise RuntimeError("TASKS_TABLE environment variable is required")
        return cls(boto3.resource("dynamodb").Table(table_name))

    @staticmethod
    def _keys(user_id: str, task_id: str) -> dict[str, str]:
        return {"PK": f"USER#{user_id}", "SK": f"TASK#{task_id}"}

    def create(self, user_id: str, task: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        item = {**self._keys(user_id, task["id"]), **task, "created_at": now, "updated_at": now}
        self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
        return item

    def list(self, user_id: str, limit: int, cursor: dict[str, Any] | None) -> dict[str, Any]:
        args: dict[str, Any] = {
            "KeyConditionExpression": Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with("TASK#"),
            "Limit": limit,
        }
        if cursor:
            args["ExclusiveStartKey"] = cursor
        result = self.table.query(**args)
        return {"items": result.get("Items", []), "last_key": result.get("LastEvaluatedKey")}

    def get(self, user_id: str, task_id: str) -> dict[str, Any] | None:
        result = self.table.get_item(Key=self._keys(user_id, task_id), ConsistentRead=True)
        return result.get("Item")

    def update(self, user_id: str, task_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        names = {f"#f{index}": field for index, field in enumerate(fields)}
        values = {f":v{index}": value for index, value in enumerate(fields.values())}
        names["#updated_at"] = "updated_at"
        values[":now"] = datetime.now(UTC).isoformat()
        assignments = [
            f"{names_key} = :v{index}"
            for index, names_key in enumerate(names)
            if names_key != "#updated_at"
        ]
        assignments.append("#updated_at = :now")
        try:
            result = self.table.update_item(
                Key=self._keys(user_id, task_id),
                UpdateExpression="SET " + ", ".join(assignments),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
                ReturnValues="ALL_NEW",
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return None
        return result.get("Attributes")

    def delete(self, user_id: str, task_id: str) -> bool:
        try:
            self.table.delete_item(
                Key=self._keys(user_id, task_id),
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return False
        return True
