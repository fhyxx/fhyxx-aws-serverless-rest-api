# Local packaging and deployment guide

This guide documents deployment commands for a future authorized operator. **This project has not been deployed, and these commands have not been run against AWS.** Never put credentials in the repository.

## Prerequisites

- Python 3.12 and Terraform 1.9 or compatible with the version constraint.
- An AWS account, approved region, least-privilege deployment role, and explicit approval for estimated costs.
- A confirmed web frontend origin for the API CORS allow list.
- A globally unique Cognito domain prefix and exact OAuth callback/logout URLs for the public frontend.
- A decision on table retention/deletion protection, log retention, alarms, and restore ownership.

## Build a Lambda artifact

Use a Linux-compatible build environment matching the Lambda architecture (ARM64) when adding native dependencies. From the project root, the packaging helper installs the pinned boto3 SDK and copies the application source into the Lambda artifact:

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/build_lambda.py
```

Review the artifact contents before use. Terraform's archive data source packages the prepared `build/lambda-package/` directory. Run the build helper again after source or dependency changes, then validate and review the generated plan. Confirm the artifact's architecture and handler import before an approved deployment.

### Windows PowerShell packaging check

The current machine exposes only Python 3.15 through `py -0p`; `py -3.12 --version` reports that no suitable runtime is installed. The requested `winget install --id Python.Python.3.12 -e` was attempted, but this Codex-managed shell could not launch `C:\Users\Fhyx\AppData\Local\Microsoft\WindowsApps\winget.exe` (`The file cannot be accessed by the system`). The Lambda packaging helper was not run with another Python version as a substitute. Run the install command from a normal PowerShell window and then open a new window:

```powershell
winget install --id Python.Python.3.12 -e
```

After Python 3.12 is installed and registered with the launcher, run these commands from a fresh project checkout (the helper intentionally refuses to overwrite existing generated output):

```powershell
$project = 'C:\Users\Fhyx\Documents\Codex\2026-11-08\chrome-plugin-chrome-openai-bundled-x20\aws-serverless-rest-api'
Set-Location $project
py -3.12 --version
py -3.12 -m venv .venv312
& .\.venv312\Scripts\python.exe -m pip install --upgrade pip
& .\.venv312\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv312\Scripts\python.exe scripts\build_lambda.py
& .\.venv312\Scripts\python.exe -c "import zipfile; p='dist/task_api.zip'; z=zipfile.ZipFile(p); assert z.testzip() is None; n=set(z.namelist()); assert 'task_api/handlers/http.py' in n and 'boto3/__init__.py' in n; print('Python 3.12 Lambda ZIP contents: verified')"
```

The final command checks the generated ZIP's integrity and confirms the handler and pinned boto3 package are present. It does not deploy or contact AWS.

## Validate, review and deploy (future operator action)

```bash
cd terraform
terraform init
terraform fmt -check -recursive .
terraform validate
terraform plan -out=tfplan
terraform show tfplan
```

Require peer review of the plan, cost estimate, IAM diff, retention settings, Cognito configuration, and CORS origin. Apply only after separate approval:

```bash
terraform apply tfplan
```

This repository's automated checks use `init -backend=false` and `validate`; they do not create AWS resources. Do not run `apply` for the purposes of this portfolio project.

The first successful `terraform init -backend=false` creates `terraform/.terraform.lock.hcl` with the selected provider checksums. Keep that lockfile under version control; Terraform uses it on later init runs unless `-upgrade` is explicitly requested. Do not delete it to bypass provider issues. The provider versions are exactly pinned in `versions.tf`.

## Windows provider initialization note

On this Windows environment, `terraform init -backend=false` could not complete. The documented LocalAppData procedure failed when PowerShell tried to create `C:\Users\Fhyx\AppData\Local\terraform.d\plugin-cache` (`Access to the path ... is denied`), then Terraform could not reach `registry.terraform.io` (`connectex: An attempt was made to access a socket in a way forbidden by its access permissions`). A retry in a project-owned temp/cache with network permission downloaded pinned provider packages but was stopped while still running and did not return a successful result. Earlier attempts reported `failed to compute checksum` with `Access is denied` on temporary `terraform-provider*` files. The project temp folder itself grants the current user FullControl and passed a direct read/write/delete probe; this does not establish permissions for LocalAppData or explain Terraform's provider-file failure. The exact Windows security/process component has not been identified. A 14-day read-only Defender event query found no matching detection/remediation/ASR block events (IDs 1116, 1117, 1121, 1122); `Get-MpThreatDetection` returned `Access denied`, so the Protection History UI could not be confirmed from this session. The subsequent `terraform -chdir=terraform validate` reports that `hashicorp/archive` and `hashicorp/aws` are missing because initialization did not install them; validation is therefore blocked in this environment. No lockfile exists because initialization did not complete. Do not disable security controls or remove a lockfile to work around this.

In a normal, non-restricted PowerShell session, set a user-owned temp and provider cache, then retry without `-upgrade`:

```powershell
$project = 'C:\Users\Fhyx\Documents\Codex\2026-11-08\chrome-plugin-chrome-openai-bundled-x20\aws-serverless-rest-api'
$env:TEMP = Join-Path $env:LOCALAPPDATA 'Temp'
$env:TMP = $env:TEMP
$env:TF_PLUGIN_CACHE_DIR = Join-Path $env:LOCALAPPDATA 'terraform.d\plugin-cache'
New-Item -ItemType Directory -Force -Path $env:TF_PLUGIN_CACHE_DIR | Out-Null
Set-Location $project
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

If the same checksum staging error occurs, inspect Windows Security Protection History and your organization's endpoint-protection logs for temporary `terraform-provider*` files under the selected temp/cache paths. Ask the device administrator for an approved exception for Terraform's official, checksum-verified provider binaries or for help with the affected folder ACL; do not broadly disable Defender. After successful initialization, retain and commit the generated lockfile; CI can then use `terraform init -backend=false -lockfile=readonly` to enforce it.

The Lambda execution role is intentionally limited to the task table and its own log group. The separate Terraform deployment identity must also have the API Gateway and Cognito management permissions, plus CloudWatch Logs delivery permissions required to configure HTTP API access logging (for example `logs:CreateLogDelivery`, `logs:PutResourcePolicy`, `logs:DescribeResourcePolicies`, and related log-delivery actions). Do not add these deployment permissions to the Lambda runtime role.

## Obtain a Cognito token and call the API

Create/authenticate a test user through Cognito managed login using authorization-code flow with PKCE. Request `openid email tasks/read tasks/write`, redeem the authorization code for an access token, and keep the token private and out of shell history/logs where practical. Use the API endpoint Terraform output and examples in `examples/requests.sh`. API Gateway should reject missing route scopes before invoking Lambda. Separately verify that one user's scoped token cannot read, update, or delete another user's task: route scopes do not confer ownership. Revoke test credentials and remove test data after an authorized test window.


## Controlled teardown after portfolio verification

The DynamoDB table and Cognito user pool have deletion protection enabled by default. Keep it enabled during normal operation. After the API has been tested and the evidence captured, remove billable resources if the project is not intended to remain online. Teardown is a two-step, reviewed operation:

1. In the deployment tfvars file, set `enable_deletion_protection = false` (the default is `true`). Review the plan and apply only this protection change.
2. Review a fresh destroy plan and, after confirming the account, region, workspace and exact resource list, run `terraform destroy`.

Example commands from the Terraform directory:

```powershell
terraform plan -var-file="terraform.tfvars" -out=disable-protection.tfplan
terraform show disable-protection.tfplan
# Apply only after confirming this plan changes the two protection settings and nothing else.
terraform apply disable-protection.tfplan
terraform plan -destroy -var-file="terraform.tfvars" -out=teardown.tfplan
terraform show teardown.tfplan
# Apply only after confirming the account, region and full resource list.
terraform apply teardown.tfplan
```

Do not delete the local Terraform state or state backups before successful teardown verification. Confirm the API, Lambda, DynamoDB table, Cognito pool/domain, log groups and IAM resources are gone in the intended account and region. Review any retained CloudWatch log groups or other manually created resources separately. If data must be retained, export and verify it before teardown; destroying the table is destructive.
