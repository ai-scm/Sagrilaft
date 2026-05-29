"""
SAGRILAFT — Infraestructura AWS (CDK Python)

Arquitectura:
  Internet → ALB (HTTPS/443) → EC2 (Docker Compose)
                                  ├─ frontend  :80
                                  └─ backend   :8000
  RDS PostgreSQL (private subnet) — app + keycloak
  S3 (uploads de documentos)
  Bedrock + SES (via IAM Role del EC2)

Uso:
  pip install -r requirements.txt
  cdk bootstrap
  cdk deploy

Secretos que debes crear en AWS Secrets Manager ANTES del deploy:
  sagrilaft/db_password         → generado automáticamente por el stack (no crear manualmente)
  sagrilaft/keycloak_admin_pass → JSON: {"password": "..."}
  sagrilaft/zoho_credentials    → JSON: {"client_id": "...", "client_secret": "...",
                                          "refresh_token": "...", "webhook_secret": "..."}
  sagrilaft/smtp_credentials    → JSON: {"username": "...", "password": "..."}
                                  (credenciales SMTP de SES — generadas en IAM → SES SMTP settings)
"""

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_rds as rds,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_certificatemanager as acm,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


# ── Parámetros — ajusta antes de hacer cdk deploy ────────────────────────────

DOMINIO          = "sagrilaft.tudominio.com"       # dominio principal de la app
DOMINIO_KEYCLOAK = "auth.tudominio.com"            # subdominio para Keycloak
EC2_KEY_PAIR     = "sagrilaft-keypair"             # nombre del key pair en tu cuenta AWS
EC2_INSTANCE     = ec2.InstanceType.of(           # t3.small = ~20 USD/mes
    ec2.InstanceClass.T3, ec2.InstanceSize.SMALL
)
RDS_INSTANCE     = ec2.InstanceType.of(           # db.t3.micro = ~15 USD/mes
    ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
)
CERT_ARN         = ""  # ARN del certificado ACM para DOMINIO y DOMINIO_KEYCLOAK
                       # Déjalo vacío → el stack creará uno (requiere validación DNS)


class SagrilaftStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── 1. VPC ────────────────────────────────────────────────────────────
        vpc = ec2.Vpc(
            self, "Vpc",
            max_azs=2,
            nat_gateways=0,                         # sin NAT para reducir costo
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # ── 2. Security Groups ────────────────────────────────────────────────

        # ALB: solo acepta 80 y 443 desde internet
        sg_alb = ec2.SecurityGroup(self, "SgAlb", vpc=vpc, description="ALB")
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80),  "HTTP")
        sg_alb.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS")

        # EC2: acepta tráfico del ALB en :80 (frontend nginx) y SSH opcional
        sg_ec2 = ec2.SecurityGroup(self, "SgEc2", vpc=vpc, description="EC2 app")
        sg_ec2.add_ingress_rule(sg_alb, ec2.Port.tcp(80),   "desde ALB → frontend")
        sg_ec2.add_ingress_rule(sg_alb, ec2.Port.tcp(8080), "desde ALB → Keycloak")
        # Descomenta para habilitar SSH temporal:
        # sg_ec2.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "SSH")

        # RDS: solo acepta conexiones desde EC2
        sg_rds = ec2.SecurityGroup(self, "SgRds", vpc=vpc, description="RDS postgres")
        sg_rds.add_ingress_rule(sg_ec2, ec2.Port.tcp(5432), "desde EC2")

        # ── 3. S3 — uploads de documentos ────────────────────────────────────
        bucket = s3.Bucket(
            self, "Uploads",
            bucket_name=f"sagrilaft-uploads-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,    # nunca se borra al destruir stack
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-tmp",
                    prefix="tmp/",
                    expiration=Duration.days(1),    # archivos temporales: 1 día
                ),
            ],
        )

        # ── 4. RDS PostgreSQL ─────────────────────────────────────────────────
        db_secret = secretsmanager.Secret(
            self, "DbSecret",
            secret_name="sagrilaft/db_password",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "sagrilaft_user"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        db = rds.DatabaseInstance(
            self, "Postgres",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
            ),
            instance_type=RDS_INSTANCE,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[sg_rds],
            database_name="sagrilaft",
            credentials=rds.Credentials.from_secret(db_secret),
            multi_az=False,                         # True para producción crítica
            storage_encrypted=True,
            deletion_protection=True,
            backup_retention=Duration.days(7),
            removal_policy=RemovalPolicy.RETAIN,
        )

        # ── 5. IAM Role para EC2 ──────────────────────────────────────────────
        role_ec2 = iam.Role(
            self, "Ec2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                # SSM para acceso sin SSH (Session Manager)
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # S3: solo el bucket de uploads
        bucket.grant_read_write(role_ec2)

        # Bedrock: invocar modelos de inferencia
        role_ec2.add_to_policy(iam.PolicyStatement(
            sid="Bedrock",
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=["*"],
        ))

        # SES: enviar correos
        role_ec2.add_to_policy(iam.PolicyStatement(
            sid="Ses",
            effect=iam.Effect.ALLOW,
            actions=["ses:SendRawEmail", "ses:SendEmail"],
            resources=["*"],
        ))

        # Secrets Manager: leer secretos en el user-data y en la app
        role_ec2.add_to_policy(iam.PolicyStatement(
            sid="Secrets",
            effect=iam.Effect.ALLOW,
            actions=["secretsmanager:GetSecretValue"],
            resources=[
                db_secret.secret_arn,
                f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:sagrilaft/*",
            ],
        ))

        # ── 6. Certificado TLS ────────────────────────────────────────────────
        if CERT_ARN:
            certificado = acm.Certificate.from_certificate_arn(
                self, "Cert", CERT_ARN
            )
        else:
            certificado = acm.Certificate(
                self, "Cert",
                domain_name=DOMINIO,
                subject_alternative_names=[DOMINIO_KEYCLOAK],
                validation=acm.CertificateValidation.from_dns(),
            )

        # ── 7. EC2 — instancia principal ──────────────────────────────────────
        # repo_url se pasa como CDK context para no hardcodear la URL del repositorio.
        # Uso: cdk deploy --context repo_url=https://github.com/org/repo.git
        # O en cdk.json: "context": { "repo_url": "https://..." }
        repo_url = self.node.try_get_context("repo_url")
        if not repo_url:
            raise ValueError(
                "Falta el contexto CDK 'repo_url'. "
                "Pásalo con: cdk deploy --context repo_url=https://github.com/org/repo.git"
            )

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            # Docker
            "apt-get update -y",
            "apt-get install -y docker.io docker-compose-v2 git awscli jq",
            "systemctl enable docker && systemctl start docker",
            "usermod -aG docker ubuntu",

            # Clonar repo (URL parametrizada — no hardcodeada en el template)
            f"git clone {repo_url} /opt/sagrilaft",
            "cd /opt/sagrilaft",

            # Leer secretos de Secrets Manager (nunca tocar estos valores en el código)
            f"DB_PASS=$(aws secretsmanager get-secret-value --secret-id sagrilaft/db_password --region {self.region} --query SecretString --output text | jq -r .password)",
            f"DB_HOST={db.db_instance_endpoint_address}",
            f"ZOHO_CREDS=$(aws secretsmanager get-secret-value --secret-id sagrilaft/zoho_credentials --region {self.region} --query SecretString --output text)",
            "ZOHO_CLIENT_ID_VAL=$(echo $ZOHO_CREDS | jq -r .client_id)",
            "ZOHO_CLIENT_SECRET_VAL=$(echo $ZOHO_CREDS | jq -r .client_secret)",
            "ZOHO_REFRESH_TOKEN_VAL=$(echo $ZOHO_CREDS | jq -r .refresh_token)",
            "ZOHO_WEBHOOK_SECRET_VAL=$(echo $ZOHO_CREDS | jq -r .webhook_secret)",
            f"KC_ADMIN_PASS=$(aws secretsmanager get-secret-value --secret-id sagrilaft/keycloak_admin_pass --region {self.region} --query SecretString --output text | jq -r .password)",
            f"SMTP_CREDS=$(aws secretsmanager get-secret-value --secret-id sagrilaft/smtp_credentials --region {self.region} --query SecretString --output text)",
            "SMTP_USER_VAL=$(echo $SMTP_CREDS | jq -r .username)",
            "SMTP_PASS_VAL=$(echo $SMTP_CREDS | jq -r .password)",

            "cat > /opt/sagrilaft/.env << ENVEOF",
            f"DATABASE_URL=postgresql+psycopg://sagrilaft_user:${{DB_PASS}}@${{DB_HOST}}:5432/sagrilaft",
            f"FRONTEND_URL=https://{DOMINIO}",
            f"UPLOAD_DIR=/app/uploads",
            f"UVICORN_WORKERS=4",
            f"AWS_REGION={self.region}",
            f"BEDROCK_MODEL_ID=arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.anthropic.claude-sonnet-4-6",
            f"STORAGE_BACKEND=s3",
            f"S3_BUCKET=sagrilaft-uploads-{self.account}",
            "ZOHO_CLIENT_ID=${ZOHO_CLIENT_ID_VAL}",
            "ZOHO_CLIENT_SECRET=${ZOHO_CLIENT_SECRET_VAL}",
            "ZOHO_REFRESH_TOKEN=${ZOHO_REFRESH_TOKEN_VAL}",
            "ZOHO_WEBHOOK_SECRET=${ZOHO_WEBHOOK_SECRET_VAL}",
            "ZOHO_SIGN_TESTING=false",
            "SMTP_HOST=email-smtp.us-east-1.amazonaws.com",
            "SMTP_PORT=587",
            "SMTP_USER=${SMTP_USER_VAL}",
            "SMTP_PASSWORD=${SMTP_PASS_VAL}",
            "SMTP_FROM=noreply@tudominio.com",
            f"KEYCLOAK_URL=http://keycloak:8080",
            f"KEYCLOAK_REALM=sagrilaft",
            f"KEYCLOAK_CLIENT_ID=sagrilaft-portal",
            f"KEYCLOAK_ISSUER_URL=https://{DOMINIO_KEYCLOAK}",
            f"KEYCLOAK_HOSTNAME={DOMINIO_KEYCLOAK}",
            f"KEYCLOAK_DB_URL=jdbc:postgresql://${{DB_HOST}}:5432/keycloak",
            "KEYCLOAK_DB_USER=sagrilaft_user",
            f"KEYCLOAK_DB_PASSWORD=${{DB_PASS}}",
            "KEYCLOAK_ADMIN=admin",
            "KEYCLOAK_ADMIN_PASSWORD=${KC_ADMIN_PASS}",
            f"VITE_KEYCLOAK_URL=https://{DOMINIO_KEYCLOAK}",
            "VITE_KEYCLOAK_REALM=sagrilaft",
            "VITE_KEYCLOAK_CLIENT_ID=sagrilaft-portal",
            "ENVEOF",

            # Crear DB keycloak en RDS
            "apt-get install -y postgresql-client",
            f"PGPASSWORD=${{DB_PASS}} psql -h ${{DB_HOST}} -U sagrilaft_user -d sagrilaft -c \"CREATE DATABASE keycloak OWNER sagrilaft_user;\" || true",

            # Levantar servicios (sin dev overlay)
            "cd /opt/sagrilaft && docker compose up --build -d",
        )

        ec2_instance = ec2.Instance(
            self, "Ec2",
            instance_type=EC2_INSTANCE,
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg_ec2,
            role=role_ec2,
            user_data=user_data,
            key_name=EC2_KEY_PAIR,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        30,                         # GB — sube si esperas muchos uploads
                        encrypted=True,
                    ),
                )
            ],
        )

        # ── 8. ALB — balanceador HTTPS ────────────────────────────────────────
        alb = elbv2.ApplicationLoadBalancer(
            self, "Alb",
            vpc=vpc,
            internet_facing=True,
            security_group=sg_alb,
        )

        # Target: EC2 en puerto 80 (nginx sirve la SPA y proxea /api)
        target_app = elbv2.ApplicationTargetGroup(
            self, "TgApp",
            vpc=vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[elbv2.InstanceTarget(ec2_instance.instance_id, 80)],
            health_check=elbv2.HealthCheck(
                path="/",
                healthy_http_codes="200-299",
            ),
        )

        # Target: EC2 en puerto 8080 (Keycloak)
        target_kc = elbv2.ApplicationTargetGroup(
            self, "TgKeycloak",
            vpc=vpc,
            port=8080,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[elbv2.InstanceTarget(ec2_instance.instance_id, 8080)],
            health_check=elbv2.HealthCheck(
                path=f"/realms/sagrilaft",
                healthy_http_codes="200-299",
            ),
        )

        # HTTPS listener: enruta según el host header
        listener_https = alb.add_listener(
            "Https",
            port=443,
            certificates=[certificado],
            default_target_groups=[target_app],
        )
        listener_https.add_action(
            "KeepDefault",
            priority=10,
            conditions=[
                elbv2.ListenerCondition.host_headers([DOMINIO_KEYCLOAK])
            ],
            action=elbv2.ListenerAction.forward([target_kc]),
        )

        # HTTP listener: redirige todo a HTTPS
        alb.add_listener(
            "Http",
            port=80,
            default_action=elbv2.ListenerAction.redirect(
                protocol="HTTPS",
                port="443",
                permanent=True,
            ),
        )

        # ── 9. Outputs ────────────────────────────────────────────────────────
        CfnOutput(self, "AlbDns",
                  value=alb.load_balancer_dns_name,
                  description="Apunta tus dominios a este CNAME en Route 53 o tu DNS")

        CfnOutput(self, "S3Bucket",
                  value=bucket.bucket_name,
                  description="Nombre del bucket S3 para uploads")

        CfnOutput(self, "RdsEndpoint",
                  value=db.db_instance_endpoint_address,
                  description="Host RDS PostgreSQL")

        CfnOutput(self, "Ec2InstanceId",
                  value=ec2_instance.instance_id,
                  description="ID de la instancia EC2 (para SSM Session Manager)")

        CfnOutput(self, "DbSecretArn",
                  value=db_secret.secret_arn,
                  description="ARN del secreto con la contraseña de la BD")
