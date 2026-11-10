# Security decisions

| Decision | Implementation | Rationale / boundary |
|---|---|---|
| Authentication and API scopes | HTTP API JWT authorizer validates Cognito issuer, client audience, signature and token time claims. Cognito resource server issues `tasks/read` and `tasks/write`; API Gateway requires one per route. | Gateway validates JWT and required OAuth scope before Lambda invocation. Local unit tests mock Lambda events and do not independently verify API Gateway scope enforcement. |
| Identity source | JWT `sub` claim from API Gateway authorizer context | The caller cannot choose the partition key owner. Request-body `user_id` is an unsupported field. |
| Authorization | `USER#{sub}` partition on every DynamoDB operation | Foreign resources resolve as not found; no global scan path exists. |
| IAM | Lambda role limited to GetItem, PutItem, UpdateItem, DeleteItem, Query on one table and log writes to one pre-created log group | No wildcard DynamoDB table access or administrative actions. |
| Data at rest | DynamoDB server-side encryption enabled | Uses the AWS-owned DynamoDB key by default; customer-managed KMS key is out of scope for this starter. |
| Recovery | DynamoDB point-in-time recovery and deletion protection enabled | Recovery window and operational restore procedure still need an owner and test. |
| Input | JSON object only; allow-listed fields; title, description, status, real ISO due-date and body-size constraints | Prevents mass assignment and bounds routine requests. |
| Responses | Stable JSON error envelope; unexpected details are logged server-side and hidden from callers | Avoids returning implementation or infrastructure details. |
| Tokens/logging | No request-body or authorization-header logging | Minimize exposure of credentials and personal data. |
| Transport | API Gateway HTTPS endpoint and AWS service TLS | TLS termination and managed service controls are AWS-managed. |
| Abuse controls | HTTP API route throttling defaults | Production rate limits, WAF, abuse monitoring, and load testing remain deployment-specific decisions. |

Before production, review threat model, account-level controls, Cognito email delivery and recovery, frontend origins, privacy/retention, backup restore process, alerting, quotas, WAF need, and incident response. No penetration test or live AWS verification is claimed.

The user-pool app client enables authorization-code flow only, uses a public-client configuration without a client secret, and associates only the standard `openid`/`email` and task API scopes. The deployment operator must replace callback/logout URL placeholders and choose a globally unique Cognito domain prefix. Use the authorization-code flow with PKCE in browser clients. Cognito custom scopes appear in access tokens; API Gateway route scopes are enforced at the gateway. Lambda must still use only the validated `sub` claim for its DynamoDB keys because scopes authorize operation classes, not ownership of individual records. Cognito authorization-code and resource-server scope behavior is documented by [AWS](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-define-resource-servers.html); API Gateway's JWT authorizer validates issuer, audience, expiry, not-before time, and signature as described in [AWS's HTTP API JWT authorizer documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html). Cognito token revocation does not make API Gateway's local JWT authorizer perform an online revocation check for every request; assess short token lifetimes or a revocation-aware authorizer for stricter immediate revocation needs.
