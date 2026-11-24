# Rol de GitHub Actions para staging (preparado, sin crear)

Hoy el CI no entra a AWS: solo revisa el código. Publicar imágenes y desplegar se hace a
mano ([guía](../../../../docs/produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md)). Esta carpeta
deja listo el primer paso para automatizar **solo staging**, sin usar el rol compartido
`GithubActionsOIDC-DeployRole` de la organización.

## Qué permite y qué no

| Archivo | Qué dice |
|---|---|
| [trust-policy.template.json](trust-policy.template.json) | Solo pueden usar el rol los jobs de `ai-scm/Sagrilaft` que declaren `environment: staging`. Otros repositorios, otras ramas sin ese ambiente y producción quedan fuera. |
| [publicar-imagenes-policy.template.json](publicar-imagenes-policy.template.json) | Subir imágenes a los 4 repositorios ECR de staging y leer los 6 parámetros SSM de build de staging. Nada más: no toca ECS, RDS, CloudFormation ni producción. |

Con eso el workflow puede correr `build_and_push_ecr_images.py --environment staging --from-ssm`,
el mismo script que se usa a mano. Activar los servicios (`deploy_release.py`) necesita más
permisos (ECS, CloudFormation, logs) y una decisión aparte; no está incluido.

## Pasos cuando se decida automatizar

**1. AWS (persona con permisos de IAM).** Reemplazar `<AWS_ACCOUNT_ID>` en los dos archivos y:

```bash
aws iam create-role --role-name SagrilaftGithubStaging \
  --assume-role-policy-document file://trust-policy.template.json \
  --tags Key=Project,Value=sagrilaft Key=Environment,Value=staging Key=ManagedBy,Value=manual
aws iam put-role-policy --role-name SagrilaftGithubStaging \
  --policy-name PublicarImagenesStaging \
  --policy-document file://publicar-imagenes-policy.template.json
```

El proveedor OIDC `token.actions.githubusercontent.com` ya existe en la cuenta.

**2. GitHub (administrador del repositorio).** En *Settings → Environments* crear `staging`,
limitarlo a la rama `main` y, si se quiere, exigir aprobación. Guardar en ese ambiente (no
en el repositorio) la variable `AWS_ROLE_STAGING` con el ARN del rol.

**3. Workflow.** Crear `.github/workflows/publicar-staging.yml` partiendo de este esquema:

```yaml
name: Publicar imágenes en staging
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  publicar:
    runs-on: ubuntu-latest
    environment: staging          # sin esto AWS rechaza el rol (ver trust policy)
    permissions:
      contents: read
      id-token: write             # solo este job puede pedir credenciales
    steps:
      - uses: actions/checkout@v4
        with: { persist-credentials: false }
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_STAGING }}
          aws-region: us-east-1
      - name: Publicar
        run: |
          CUENTA=$(aws sts get-caller-identity --query Account --output text)
          python3 scripts/despliegue/build_and_push_ecr_images.py \
            --environment staging --from-ssm --account "$CUENTA" --region us-east-1 \
            --tag "$GITHUB_SHA" --manifest "$RUNNER_TEMP/ecr-manifest.json"
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ecr-manifest-${{ github.sha }}-${{ github.run_attempt }}
          path: ${{ runner.temp }}/ecr-manifest.json
```

El manifiesto que se guarda al final es el mismo que pide el plan de `deploy_release.py`.

La prueba `tests/contracts/test_ci_sin_aws.py` comprueba que estas políticas sigan limitadas
a staging.
