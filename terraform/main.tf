data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../build/lambda-package"
  output_path = var.lambda_artifact_path
}

resource "aws_dynamodb_table" "tasks" {
  name         = "${var.project_name}-tasks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }
  server_side_encryption {
    enabled = true
  }
  deletion_protection_enabled = var.enable_deletion_protection
  tags                        = { Project = var.project_name }
}

resource "aws_cognito_user_pool" "users" {
  name                     = "${var.project_name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  deletion_protection = var.enable_deletion_protection ? "ACTIVE" : "INACTIVE"
  tags                = { Project = var.project_name }
}

resource "aws_cognito_resource_server" "tasks" {
  identifier   = "tasks"
  name         = "${var.project_name}-tasks-api"
  user_pool_id = aws_cognito_user_pool.users.id

  scope {
    scope_name        = "read"
    scope_description = "Read tasks owned by the authenticated user."
  }
  scope {
    scope_name        = "write"
    scope_description = "Create, update, and delete tasks owned by the authenticated user."
  }
}

resource "aws_cognito_user_pool_client" "api" {
  name                                 = "${var.project_name}-api-client"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes = [
    "openid",
    "email",
    "${aws_cognito_resource_server.tasks.identifier}/read",
    "${aws_cognito_resource_server.tasks.identifier}/write",
  ]
  supported_identity_providers = ["COGNITO"]
  callback_urls                = var.cognito_callback_urls
  logout_urls                  = var.cognito_logout_urls
  access_token_validity        = 60
  id_token_validity            = 60
  refresh_token_validity       = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "api" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = var.log_retention_days
  tags              = { Project = var.project_name }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${var.project_name}"
  retention_in_days = var.log_retention_days
  tags              = { Project = var.project_name }
}

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = { Project = var.project_name }
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project_name}-tasks-and-logs"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.tasks.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name    = var.project_name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "task_api.handlers.http.lambda_handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10
  memory_size      = 256
  architectures    = ["arm64"]
  environment {
    variables = { TASKS_TABLE = aws_dynamodb_table.tasks.name }
  }
  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = { Project = var.project_name }
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-http"
  protocol_type = "HTTP"
  cors_configuration {
    allow_headers = ["authorization", "content-type"]
    allow_methods = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allow_origins = ["https://localhost"]
    max_age       = 300
  }
  tags = { Project = var.project_name }
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.http.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.project_name}-cognito-jwt"
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.api.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}

locals {
  routes = {
    "POST /tasks"        = "tasks/write"
    "GET /tasks"         = "tasks/read"
    "GET /tasks/{id}"    = "tasks/read"
    "PATCH /tasks/{id}"  = "tasks/write"
    "DELETE /tasks/{id}" = "tasks/write"
  }
}

resource "aws_apigatewayv2_route" "tasks" {
  for_each             = local.routes
  api_id               = aws_apigatewayv2_api.http.id
  route_key            = each.key
  target               = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.cognito.id
  authorization_scopes = [each.value]
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format = jsonencode({
      requestId = "$context.requestId"
      routeKey  = "$context.routeKey"
      status    = "$context.status"
      sourceIp  = "$context.identity.sourceIp"
    })
  }
  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
  tags = { Project = var.project_name }
}

resource "aws_lambda_permission" "apigateway" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
