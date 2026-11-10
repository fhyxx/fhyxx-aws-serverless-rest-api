"""Keep the published contract aligned with API Gateway route scopes."""

import re
from pathlib import Path

import yaml


def test_openapi_documents_scope_for_each_route():
    document = yaml.safe_load(Path("openapi.yaml").read_text(encoding="utf-8"))
    assert document["openapi"] == "3.1.0"
    expected = {
        "/tasks": {"get": "tasks/read", "post": "tasks/write"},
        "/tasks/{id}": {
            "get": "tasks/read",
            "patch": "tasks/write",
            "delete": "tasks/write",
        },
    }
    for path, methods in expected.items():
        for method, scope in methods.items():
            operation = document["paths"][path][method]
            assert operation["security"] == [{"CognitoOAuth": [scope]}]
            assert scope in operation["description"]


def test_terraform_routes_bind_each_scope_to_the_correct_method():
    terraform = Path("terraform/main.tf").read_text(encoding="utf-8")
    expected = {
        "POST /tasks": "tasks/write",
        "GET /tasks": "tasks/read",
        "GET /tasks/{id}": "tasks/read",
        "PATCH /tasks/{id}": "tasks/write",
        "DELETE /tasks/{id}": "tasks/write",
    }
    for route, scope in expected.items():
        declaration = re.escape(f'"{route}"') + r"\s*=\s*" + re.escape(f'"{scope}"')
        assert re.search(declaration, terraform)
    assert re.search(r"route_key\s*=\s*each\.key", terraform)
    assert re.search(r"authorization_scopes\s*=\s*\[each\.value\]", terraform)
