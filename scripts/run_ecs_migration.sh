#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:=us-east-1}"
: "${ECS_CLUSTER_NAME:?Set ECS_CLUSTER_NAME from the CDK output EcsClusterName}"
: "${ECS_MIGRATION_TASK_DEFINITION_ARN:?Set ECS_MIGRATION_TASK_DEFINITION_ARN from the CDK output EcsMigrationTaskDefinitionArn}"
: "${ECS_SECURITY_GROUP_ID:?Set ECS_SECURITY_GROUP_ID from the CDK output EcsSecurityGroupId}"
: "${ECS_PRIVATE_SUBNET_IDS:?Set ECS_PRIVATE_SUBNET_IDS as comma-separated private subnet IDs}"

aws ecs run-task \
  --region "$AWS_REGION" \
  --cluster "$ECS_CLUSTER_NAME" \
  --launch-type FARGATE \
  --task-definition "$ECS_MIGRATION_TASK_DEFINITION_ARN" \
  --network-configuration "awsvpcConfiguration={subnets=[$ECS_PRIVATE_SUBNET_IDS],securityGroups=[$ECS_SECURITY_GROUP_ID],assignPublicIp=DISABLED}"
