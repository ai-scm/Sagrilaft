# Etiquetado de recursos AWS

Función única: criterio para identificar en AWS a qué sistema, ambiente y función
pertenece cada recurso de SAGRILAFT, y cómo se administra. La cuenta es compartida
con otros proyectos: estas etiquetas son la forma de separar lo nuestro.

## Las cuatro etiquetas

| Etiqueta | Valores | Responde |
|---|---|---|
| `Project` | `sagrilaft` | ¿De qué sistema es? |
| `Environment` | `staging`, `prod` | ¿De qué ambiente? |
| `Component` | Ver tabla siguiente | ¿Qué función cumple? |
| `ManagedBy` | `cdk`, `manual`, `autoescalado` | ¿Quién lo crea y mantiene? |

Claves en inglés con mayúscula inicial; valores en minúscula con guiones.

`ManagedBy=cdk` significa que el recurso está en el código: un cambio manual se pierde
en el siguiente despliegue. `manual` y `autoescalado` marcan lo que vive fuera del
código y nadie mantiene automáticamente.

## Componentes

| `Component` | Recursos |
|---|---|
| `red` | VPC, subredes, NAT, IP elástica, Internet Gateway, tablas de rutas, grupos de seguridad, endpoint S3 |
| `balanceador` | ALB |
| `cortafuegos-web` | WAF |
| `plataforma-contenedores` | Cluster ECS, rol de ejecución compartido, espacio Cloud Map |
| `backend` | Servicio, definición de tarea, rol, logs, target group y repositorio ECR del backend |
| `formulario-publico` | Ídem, formulario público |
| `portal-interno` | Ídem, portal interno |
| `keycloak` | Ídem, Keycloak |
| `listas-worker` | Servicio, definición de tarea, rol y logs del trabajador de listas |
| `migraciones` | Definición de tarea y logs de migraciones (usa el rol del backend) |
| `base-datos` | RDS PostgreSQL y su grupo de subredes |
| `almacenamiento` | Bucket S3 de archivos |
| `secretos` | Secretos de Secrets Manager |
| `configuracion` | Parámetros SSM de `/sagrilaft/<ambiente>/config/` |
| `notificaciones` | Tema SNS de alertas |
| `observabilidad` | Alarmas y dashboards de CloudWatch |

## Dónde se aplica

- **Código:** [`infra/sagrilaft/lib/etiquetas.ts`](../../../infra/sagrilaft/lib/etiquetas.ts)
  define la lista cerrada de componentes; `sagrilaft-stack.ts` asigna cada bloque.
  Un valor fuera de la lista no compila.
- **Prueba:** [`infra/sagrilaft/test/etiquetas.test.ts`](../../../infra/sagrilaft/test/etiquetas.test.ts)
  falla si un recurso que admite etiquetas queda sin alguna de las cuatro, si aparece
  un tipo sin etiquetas no previsto o si el stack crea un recurso compartido.

## Qué no lleva etiquetas de SAGRILAFT

**Recursos compartidos con otros proyectos.** El stack los importa; nunca los crea
ni los etiqueta:

- certificado comodín `*.ia.blend360.com`;
- zona DNS e identidad SES `ia.blend360.com` (los registros DNS de SAGRILAFT sí son
  del stack, pero Route 53 no admite etiquetas en registros);
- rol de despliegue de GitHub y recursos de bootstrap de CDK.

**Tipos que AWS no permite etiquetar:** rutas, reglas de grupos de seguridad,
asociaciones de subred y de WAF, políticas IAM, listeners y sus reglas, registros
DNS, suscripciones SNS, objetivos y políticas de autoescalado. Se identifican por el
stack `SagrilaftStack-<ambiente>` al que pertenecen.

## Recursos fuera de CDK

| Recurso | Origen | `ManagedBy` |
|---|---|---|
| Secreto `sagrilaft/prod/zoho_credentials` | Creado a mano; el stack de prod lo importa | `manual` |
| Parámetro `/sagrilaft/prod/config/PORTAL_URL` | Creado a mano; se conserva ([decisión](VARIABLES_DE_ENTORNO.md)) | `manual` |
| Alarmas `TargetTracking-service/sagrilaft-<ambiente>/…` | Las crea el autoescalado del backend; se recrean al cambiar la política | `autoescalado` |
| Snapshots manuales de RDS | Tomados a mano (por ejemplo antes de una migración) | `manual` |
| Snapshots automáticos de RDS | Los crea RDS y heredan las etiquetas de la base | `cdk` (heredado) |
| Logs de Container Insights y zonas `sagrilaft-<ambiente>.local` | ECS y Cloud Map; copian etiquetas solo al crearse | — |
| Tareas ECS en ejecución | Heredan las del servicio al arrancar | heredado |

Las filas `manual` y `autoescalado` se etiquetan con un procedimiento aparte del
despliegue de CDK.

## Snapshots de RDS

La base tiene `CopyTagsToSnapshot` activo y **no se modifica**:

- **Automáticos:** heredan las etiquetas de la base (`Component=base-datos`,
  `ManagedBy=cdk`). Forman parte del ciclo de vida de la instancia.
- **Manuales:** se crean **con etiquetas explícitas** y `ManagedBy=manual`. Cuando
  se pasan etiquetas al crear un snapshot, RDS no copia las de la base, así que hay
  que incluir las cuatro.

```bash
aws rds create-db-snapshot \
  --db-instance-identifier <INSTANCIA_RDS_DEL_AMBIENTE> \
  --db-snapshot-identifier sagrilaft-<ambiente>-<motivo>-<AAAAMMDD> \
  --tags Key=Project,Value=sagrilaft \
         Key=Environment,Value=<ambiente> \
         Key=Component,Value=base-datos \
         Key=ManagedBy,Value=manual
```

Se pueden agregar etiquetas propias del motivo (por ejemplo `release=<sha>` antes de
una migración). Después, comprobar que quedaron las cuatro:

```bash
aws rds list-tags-for-resource \
  --resource-name arn:aws:rds:us-east-1:<CUENTA>:snapshot:sagrilaft-<ambiente>-<motivo>-<AAAAMMDD>
```

## Buscar recursos en la consola

En **Resource Groups → Tag Editor**, región `us-east-1`, tipos "All supported":

- todo SAGRILAFT de producción: `Project=sagrilaft` y `Environment=prod`;
- todo el backend de producción: además `Component=backend`;
- lo que está fuera del código: `Project=sagrilaft` y `ManagedBy=manual`.
