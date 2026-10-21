// Cuenta objetivo para staging/prod. Viene del entorno (CUENTA_AWS). Sin valor, app.ts falla cerrado.
export const TARGET_ACCOUNT = process.env.CUENTA_AWS ?? '';
export const DEFAULT_REGION = 'us-east-1';
// Los scripts de deploy pasan -c bedrockModelId; este valor solo aplica sin -c.
export const DEFAULT_BEDROCK_MODEL_ID = 'amazon.nova-pro-v1:0';

// Nombre de la base de datos RDS PostgreSQL compartida por backend y Keycloak.
// Unica fuente de verdad: database.ts la usa para crearla; ecs-fargate.ts y
// sagrilaft-stack.ts solo la referencian, nunca la redeclaran como literal.
export const SAGRILAFT_DB_NAME = 'sagrilaft';

