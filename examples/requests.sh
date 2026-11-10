#!/usr/bin/env bash
# Replace placeholders locally. Do not commit real tokens or deployed endpoints.
API_BASE="${API_BASE:-https://example.execute-api.us-east-1.amazonaws.com}"
TOKEN="${TOKEN:?Set TOKEN to a short-lived Cognito JWT in your local shell}"
# TOKEN must be a Cognito access token issued through authorization-code + PKCE
# with the tasks/read and tasks/write scopes requested. GET endpoints require
# tasks/read; POST/PATCH/DELETE require tasks/write. API Gateway enforces scopes.
# Lambda independently enforces ownership from the validated JWT sub claim.
# Never send a user_id in a body/query; the API rejects unsupported body fields.
# Cognito managed-login authorization-code request (implement S256 PKCE in the
# browser client; use returned access token as TOKEN, never an ID token):
# https://$COGNITO_DOMAIN/oauth2/authorize?response_type=code&client_id=$CLIENT_ID&redirect_uri=$CALLBACK_URL&scope=openid%20email%20tasks%2Fread%20tasks%2Fwrite&code_challenge_method=S256&code_challenge=$PKCE_CHALLENGE&state=$CSRF_STATE

curl --fail-with-body -X POST "$API_BASE/tasks" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Prepare quarterly report","description":"Collect approved figures","due_date":"2026-12-01"}'

curl --fail-with-body "$API_BASE/tasks?limit=20" -H "Authorization: Bearer $TOKEN"

# Substitute a task UUID returned by POST; requests only affect the authenticated owner.
TASK_ID="${TASK_ID:-00000000-0000-4000-8000-000000000000}"
curl --fail-with-body "$API_BASE/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN"
curl --fail-with-body -X PATCH "$API_BASE/tasks/$TASK_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}'
curl --fail-with-body -X DELETE "$API_BASE/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN"
