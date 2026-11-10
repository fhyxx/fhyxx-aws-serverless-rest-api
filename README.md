# AWS Serverless Task Management REST API

A production-minded starter REST API using Python 3.12, AWS Lambda, API Gateway HTTP API, Amazon Cognito JWT authentication, DynamoDB and Terraform. All local tests use mocked AWS services. **No AWS resources have been deployed or live-verified, and no real credentials are required.**

## Features

- `POST /tasks`, `GET /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, and `DELETE /tasks/{id}`.
- Cognito resource server defines `tasks/read` and `tasks/write`; API Gateway enforces the appropriate scope on every route. Lambda independently obtains owner identity only from the validated JWT `sub` claim.
- Cognito authorization-code OAuth flow is enabled for a public app client; use PKCE and configure a unique managed-login domain plus the real frontend callback/logout URLs before deployment.
- DynamoDB single table with `USER#{sub}` partition keys and `TASK#{uuid}` sort keys; every operation is scoped to the signed-in owner.
- Input allow-lists and bounds, consistent JSON errors, standard status codes, bounded page size, opaque continuation cursor, conditional writes and structured server-side logging.
- Separated HTTP handler, validation, service and DynamoDB repository layers.
- Terraform for HTTP API, Lambda, Cognito, DynamoDB, scoped IAM and CloudWatch Logs; PITR, encryption and DynamoDB deletion protection are enabled.
- OpenAPI 3.1 contract, security/architecture decisions, example client requests and future deployment guidance.

## Project structure

```text
aws-serverless-rest-api/
├── .github/workflows/ci.yml
├── docs/                     # Architecture, security and deployment notes
├── examples/                 # Example curl requests
├── scripts/                  # Reproducible Lambda packaging helper
├── src/task_api/
│   ├── handlers/http.py      # API Gateway v2 routing and response mapping
│   ├── validation.py         # JSON, fields and cursor validation
│   ├── service.py            # Task use cases
│   └── repository.py         # DynamoDB persistence
├── terraform/                # AWS infrastructure definition (not deployed)
├── tests/                    # Pytest with moto DynamoDB mocks
├── openapi.yaml
├── pyproject.toml
└── requirements.txt
```

## Local setup and checks

Python 3.12 is required by the package metadata. From this directory, in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
ruff check src tests
ruff format --check src tests
```

Terraform checks (Terraform 1.6 or later and provider download access required):

```powershell
terraform fmt -check -recursive terraform
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

The CI workflow runs those checks on Python 3.12 and Terraform 1.16.6. Terraform provider versions are pinned and the committed lockfile is checked in read-only mode on CI. Terraform init downloads providers but does not create AWS resources. No `terraform plan` or `apply` is needed for local validation.

## API contract and example

See [OpenAPI 3.1](openapi.yaml) and [`examples/requests.sh`](examples/requests.sh). Include an `Authorization: Bearer <Cognito JWT>` header. Create body example:

```json
{
  "title": "Prepare quarterly report",
  "description": "Collect approved figures",
  "status": "open",
  "due_date": "2026-12-01"
}
```

List requests accept `limit` from 1 to 100 (default 20) and an opaque `cursor` returned by the preceding response. A task owned by another user responds as `404 not_found`, matching a missing task.

## Architecture and security

Read [architecture](docs/architecture.md), [security decisions](docs/security-decisions.md), and [deployment instructions](docs/deployment.md). The JWT authorizer checks the Cognito issuer, signature, expiry, not-before time and client audience; route-specific custom scopes are checked by API Gateway. Owner keys are generated from the trusted `sub` claim. Scope enforcement is not ownership enforcement: bodies cannot set identity or storage keys, and every DynamoDB access remains user-partition scoped. Unit tests exercise the Lambda boundary with mocked JWT claims; they do not simulate API Gateway's scope enforcement. DynamoDB IAM is restricted to one table; PITR, service encryption and deletion protection are configured. API and Lambda logs have explicit retention.

## Limitations and decisions before production

- No idempotency keys or optimistic locking; concurrent PATCH requests can overwrite the same field.
- No status/time secondary index, free-text search, attachment storage, audit trail, soft delete, multi-region recovery, WAF or custom domain.
- API CORS uses `https://localhost` as a narrow placeholder. Set the exact approved frontend origin before deployment.
- Cognito user onboarding/email delivery, account recovery policy, production quotas, observability alarms, operational restore exercise and privacy review need environment-specific decisions.
- No load, penetration, disaster recovery or live AWS integration tests have been performed.

## Cost and scope warning

This is an implementation portfolio example, not a cost quote or a promise of free operation. API Gateway requests, Lambda duration, DynamoDB reads/writes and storage, Cognito usage, CloudWatch ingestion/retention, data transfer, PITR and related services can incur charges depending on Region and workload. The Terraform configuration has not been priced or deployed. Review the current AWS Pricing Calculator and service terms, set account budgets/alerts, and obtain approval before any deployment. This project makes no AWS API calls in tests and creates no AWS resources.
