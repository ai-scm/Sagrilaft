export const TARGET_ACCOUNT = '874641912777';
export const DEFAULT_REGION = 'us-east-1';
export const DEFAULT_BEDROCK_MODEL_ID =
  'arn:aws:bedrock:us-east-1:874641912777:inference-profile/us.anthropic.claude-sonnet-4-6';

// Nombre de la base de datos RDS PostgreSQL compartida por backend y Keycloak.
// Unica fuente de verdad: database.ts la usa para crearla; ecs-fargate.ts y
// sagrilaft-stack.ts solo la referencian, nunca la redeclaran como literal.
export const SAGRILAFT_DB_NAME = 'sagrilaft';

