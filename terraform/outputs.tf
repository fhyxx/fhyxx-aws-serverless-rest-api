output "api_endpoint" {
  description = "HTTP API base URL."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.users.id
}

output "cognito_app_client_id" {
  value = aws_cognito_user_pool_client.api.id
}

output "cognito_oauth_domain" {
  description = "Managed-login base URL for the authorization-code flow."
  value       = "https://${aws_cognito_user_pool_domain.api.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_resource_server_scopes" {
  description = "OAuth scopes enforced by the API Gateway routes."
  value       = ["tasks/read", "tasks/write"]
}

output "tasks_table_name" {
  value = aws_dynamodb_table.tasks.name
}
