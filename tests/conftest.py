"""Shared mocked AWS resources and API Gateway event builder."""

import json

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def api(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("TASKS_TABLE", "tasks-test")
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="tasks-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        from task_api.handlers.http import lambda_handler

        yield lambda_handler


def event(method, path, *, sub="user-a", body=None, query=None, task_id=None):
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "headers": {},
        "queryStringParameters": query,
        "pathParameters": {"id": task_id} if task_id else None,
        "requestContext": {
            "requestId": "test-request",
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"sub": sub}}},
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }
