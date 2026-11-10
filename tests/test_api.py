"""End-to-end handler tests against a mocked DynamoDB table."""

import json

from conftest import event


def call(api, method, path, **kwargs):
    result = api(event(method, path, **kwargs), None)
    body = json.loads(result["body"]) if result["body"] else None
    return result["statusCode"], body


def test_crud_round_trip(api):
    status, body = call(
        api, "POST", "/tasks", body={"title": "Prepare release", "description": "Ship v1"}
    )
    assert status == 201
    task = body["task"]
    task_id = task["id"]
    assert "PK" not in task and "SK" not in task
    assert task["status"] == "open"
    assert task["description"] == "Ship v1"

    status, body = call(api, "GET", f"/tasks/{task_id}", task_id=task_id)
    assert status == 200 and body["task"]["title"] == "Prepare release"

    status, body = call(
        api, "PATCH", f"/tasks/{task_id}", task_id=task_id, body={"status": "completed"}
    )
    assert status == 200 and body["task"]["status"] == "completed"

    status, body = call(api, "DELETE", f"/tasks/{task_id}", task_id=task_id)
    assert status == 204 and body is None
    status, body = call(api, "GET", f"/tasks/{task_id}", task_id=task_id)
    assert status == 404 and body["error"]["code"] == "not_found"


def test_list_is_scoped_to_cognito_subject_and_ignores_body_user_id(api):
    status, body = call(api, "POST", "/tasks", body={"title": "Mine", "user_id": "user-b"})
    assert status == 400
    status, body = call(api, "POST", "/tasks", body={"title": "Mine"})
    assert status == 201
    mine_id = body["task"]["id"]
    status, body = call(api, "POST", "/tasks", sub="user-b", body={"title": "Theirs"})
    assert status == 201
    theirs_id = body["task"]["id"]
    status, body = call(api, "GET", "/tasks", sub="user-a", query={"user_id": "user-b"})
    assert status == 200
    assert [item["id"] for item in body["items"]] == [mine_id]
    status, body = call(api, "GET", "/tasks", sub="user-b")
    assert status == 200
    assert [item["id"] for item in body["items"]] == [theirs_id]


def test_cross_user_access_is_denied_as_not_found(api):
    _, created = call(api, "POST", "/tasks", body={"title": "Private"})
    task_id = created["task"]["id"]
    for method, body in [("GET", None), ("PATCH", {"title": "Tampered"}), ("DELETE", None)]:
        status, payload = call(
            api, method, f"/tasks/{task_id}", sub="other-user", task_id=task_id, body=body
        )
        assert status == 404
        assert payload["error"]["code"] == "not_found"
    status, payload = call(api, "GET", f"/tasks/{task_id}", sub="user-a", task_id=task_id)
    assert status == 200
    assert payload["task"]["title"] == "Private"


def test_validation_and_malformed_json(api):
    status, body = call(api, "POST", "/tasks", body={"title": "  "})
    assert status == 400 and body["error"]["code"] == "invalid_field"
    status, body = call(api, "POST", "/tasks", body={"title": "ok", "admin": True})
    assert status == 400 and body["error"]["code"] == "unknown_fields"
    status, body = call(api, "POST", "/tasks", body={"title": "ok", "status": []})
    assert status == 400 and body["error"]["code"] == "invalid_status"
    status, body = call(api, "POST", "/tasks", body={"title": "ok", "due_date": "2026-02-30"})
    assert status == 400 and body["error"]["code"] == "invalid_due_date"
    invalid = event("POST", "/tasks", body=None)
    invalid["body"] = "{bad json"
    result = api(invalid, None)
    assert result["statusCode"] == 400
    invalid["body"] = "[]"
    assert api(invalid, None)["statusCode"] == 400


def test_missing_record_patch_and_delete(api):
    assert call(api, "PATCH", "/tasks/absent", task_id="absent", body={"title": "x"})[0] == 404
    assert call(api, "DELETE", "/tasks/absent", task_id="absent")[0] == 404


def test_pagination_cursors_walk_all_items(api):
    for title in ["A", "B", "C"]:
        assert call(api, "POST", "/tasks", body={"title": title})[0] == 201
    status, first = call(api, "GET", "/tasks", query={"limit": "2"})
    assert status == 200
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    status, second = call(
        api, "GET", "/tasks", query={"limit": "2", "cursor": first["next_cursor"]}
    )
    assert status == 200
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert len({item["id"] for item in first["items"] + second["items"]}) == 3


def test_bad_pagination_parameters(api):
    assert call(api, "GET", "/tasks", query={"limit": "0"})[0] == 400
    assert call(api, "GET", "/tasks", query={"limit": "nope"})[0] == 400
    assert call(api, "GET", "/tasks", query={"cursor": "not-base64!"})[0] == 400
    call(api, "POST", "/tasks", body={"title": "Private cursor A"})
    call(api, "POST", "/tasks", body={"title": "Private cursor B"})
    _, page = call(api, "GET", "/tasks", query={"limit": "1"})
    status, payload = call(
        api, "GET", "/tasks", sub="other-user", query={"cursor": page["next_cursor"]}
    )
    assert status == 400 and payload["error"]["code"] == "invalid_cursor"


def test_missing_authentication_is_unauthorized(api):
    request = event("GET", "/tasks")
    del request["requestContext"]["authorizer"]
    result = api(request, None)
    assert result["statusCode"] == 401
    assert json.loads(result["body"])["error"]["code"] == "unauthorized"
