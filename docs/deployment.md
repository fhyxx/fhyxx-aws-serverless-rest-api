# Local packaging and deployment guide

This project has **not been deployed to AWS or live-verified**. The repository contains a tested application, a locally inspected Lambda package, and validated Terraform configuration. Deployment is a separate, optional activity that can create billable resources. Do not run `terraform apply` or `terraform destroy` without explicit authorization for the exact operation and a reviewed plan. Never put credentials in the repository.

## Prerequisites

- Python 3.12 for the application and Lambda package.
- Terraform 1.16.6 (the CI version) or a compatible version satisfying `versions.tf`.
- An AWS account, approved region, least-privilege deployment role, and explicit approval for estimated costs before deployment.
- A confirmed browser origin for the API CORS allow list. The current default is `http://localhost:3000`; do not expose a wildcard origin.
- A globally unique Cognito domain prefix and exact OAuth callback/logout URLs. Replace the example values before deployment.
- A decision on table retention/deletion protection, log retention, alarms, and restore ownership.

## Build a Lambda artifact

The packaging helper installs the pinned Boto3 SDK and stages the application source into the Lambda package directory. From the project root:

```powershell
py -3.12 -m venv .venv312
& .\.venv312\Scripts\python.exe -m pip install --upgrade pip
& .\.venv312\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv312\Scripts\python.exe scripts\build_lambda.py
```

Review the artifact contents before use. Terraform's archive data source packages the prepared `build/lambda-package/` directory. Rebuild after source or dependency changes. Confirm the artifact's architecture and handler import before an approved deployment. If native dependencies are introduced, build in a Linux-compatible environment matching the configured Lambda ARM64 architecture.

### Previously verified local artifact

The local `dist/task_api.zip` was built using Python 3.12.10 and inspected. At the time of inspection:

- ZIP integrity check passed; the handler and pinned runtime dependencies were present.
- Handler import and Python compilation passed under Python 3.12.10.
- No native extension modules or private-key files were found.
- Compressed size was approximately 14.1 MB and uncompressed size approximately 20.1 MB.
- SHA-256: `8B24A0192963774F6F874702E3A8A7E85E4E418CB65B0F4384625A3B66BC4BFB`.

This records a previous local artifact inspection, not a claim that the artifact is rebuilt from every future source revision or that it has executed on AWS ARM64 hardware. Rebuild and re-inspect it whenever application source or dependencies change.

## Validate, review and deploy (future operator action)

From the repository root:

```powershell
terraform fmt -check -recursive terraform
terraform -chdir=terraform init -backend=false -lockfile=readonly
terraform -chdir=terraform validate
terraform -chdir=terraform plan -out=tfplan
terraform -chdir=terraform show tfplan
```

The first three commands validate configuration and providers; they do not create AWS resources. CI runs Terraform 1.16.6, checks formatting, initializes providers using the committed lockfile in read-only mode, and validates the configuration.

Before any deployment, review the active AWS account and Region, Terraform workspace and state, resource names, IAM changes, retention settings, Cognito configuration, CORS origin, and estimated costs. Confirm the Cognito domain prefix is globally available and callback/logout URLs match the intended client. The deployment identity needs the API Gateway and Cognito management permissions, plus CloudWatch Logs delivery permissions required to configure HTTP API access logging (for example `logs:CreateLogDelivery`, `logs:PutResourcePolicy`, `logs:DescribeResourcePolicies`, and related log-delivery actions). Do not add these deployment permissions to the Lambda runtime role.

A plan is not deployment approval. Only after the owner explicitly approves the exact reviewed plan may an authorized operator run:

```powershell
terraform -chdir=terraform apply tfplan
```

This creates AWS resources and can incur charges. The project has no live endpoint until deployment and post-deployment verification are completed.

## Configuration decisions required before deployment

- Set `cognito_domain_prefix` to a globally unique prefix.
- Replace the example callback and logout URLs with exact HTTPS URLs for the real frontend, or the intended localhost URLs for a local demonstration.
- Set `cors_allowed_origins` to the exact frontend origin.
- Review `aws_region`, `project_name`, log retention and deletion protection.
- Establish account budgets/alerts and estimate service charges for API Gateway, Lambda, DynamoDB, Cognito, CloudWatch Logs, PITR, and data transfer.
- Decide who owns user onboarding/email delivery, recovery, monitoring, backups, restore testing, incident response, and data retention.

The DynamoDB table uses on-demand billing, point-in-time recovery, server-side encryption and deletion protection by default. Cognito user-pool deletion protection is also enabled by default. Keep protection enabled during normal operation.

## Obtain a Cognito token and call the API

After an explicitly approved deployment, create/authenticate a test user through Cognito managed login using authorization-code flow with PKCE. Request `openid email tasks/read tasks/write`, redeem the authorization code for an access token, and keep the token private and out of shell history/logs where practical. Use the API endpoint Terraform output and examples in `examples/requests.sh`.

Verify that API Gateway rejects missing route scopes before invoking Lambda. Separately verify that one user's scoped token cannot read, update, or delete another user's task: route scopes do not confer ownership. Revoke test credentials and remove test data after the authorized test window.

## Controlled teardown after an approved temporary deployment

Do not destroy resources until the owner has explicitly approved teardown and the account, Region, workspace, state and resource list have been checked. The DynamoDB table and Cognito user pool have deletion protection enabled by default.

1. In the deployment tfvars file, set `enable_deletion_protection = false`. Review and apply only the protection change, after approval.
2. Generate a fresh destroy plan, inspect every resource, and obtain explicit approval before applying it.

Example commands from the Terraform directory:

```powershell
terraform plan -var-file="terraform.tfvars" -out=disable-protection.tfplan
terraform show disable-protection.tfplan
# Apply only after confirming this plan changes the intended protection settings and nothing else.
terraform apply disable-protection.tfplan
terraform plan -destroy -var-file="terraform.tfvars" -out=teardown.tfplan
terraform show teardown.tfplan
# Apply only after explicit approval of this exact destroy plan.
terraform apply teardown.tfplan
```

Do not delete local Terraform state or state backups before successful teardown verification. Confirm the API, Lambda, DynamoDB table, Cognito pool/domain, log groups and IAM resources are gone in the intended account and Region. Review any retained CloudWatch log groups or other manually created resources separately. If data must be retained, export and verify it before teardown; destroying the table is destructive.
