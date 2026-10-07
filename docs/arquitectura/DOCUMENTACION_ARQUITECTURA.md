# Documentación de Arquitectura Cloud y Despliegue - SAGRILAFT

Función única: topología, recursos, permisos y fundamentos AWS. Estado en [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md); ejecución en [Checklist](../produccion/CHECKLIST_CORTE_PRODUCCION.md).

Este documento explica la infraestructura del sistema, cómo está desplegado, qué componentes tecnológicos utilizamos y, lo más importante, **por qué** tomamos cada decisión arquitectónica basándonos en los requisitos de negocio, seguridad y estabilización para Producción.

---

## 1. Visión General de la Arquitectura
El sistema SAGRILAFT es una plataforma **100% Serverless y Contenerizada** que vive dentro de la nube de AWS.
Esto significa que no tenemos un servidor tradicional (computadora) encendido en una oficina al que haya que darle mantenimiento, sino que empaquetamos nuestro código en contenedores (Docker) y le decimos a AWS: *"Toma, ejecuta esto en tu nube y danos la memoria y procesador necesarios"*.

**¿Por qué lo hicimos así?**
Para lograr escalabilidad masiva, eliminar el mantenimiento de hardware y garantizar que el ambiente local de los programadores sea **exactamente igual** al entorno de Producción (Staging/Prod).

---

## 2. Componentes Principales de la Infraestructura (IaaC)

Toda la red está programada en código (usando AWS CDK en `infra/sagrilaft/lib`). Si borramos todo por error, podemos recrear la arquitectura completa idéntica en 15 minutos.

### A. AWS ECS Fargate (El Cerebro Computacional)
Aquí viven nuestros 4 componentes de software: El Backend (FastAPI), el Portal Interno, el Formulario Público y el gestor de usuarios (Keycloak).
*   **¿Por qué Fargate?** Porque es *Serverless*. AWS gestiona los fierros. Si un contenedor se daña, AWS lanza otro automáticamente.
*   **Decisión Core:** el valor se configura por ambiente mediante CDK. Staging se desplegó con `desiredCount=1` para validar el flujo con un costo controlado; producción se prepara con `desiredCount=2` o más donde aplique para alta disponibilidad. El valor efectivo debe comprobarse en la salida del despliegue, no inferirse del diagrama.
*   **Autoscaling (actualizado 2026-07-30):** Solo el servicio **Backend** escala automáticamente (`service.autoScaleTaskCount`, target tracking en CPU 60% / memoria 70%, hasta `backendMaxCapacity` tasks, default 4). Es el único de los 4 con carga variable real (extracción con Bedrock, generación de PDF). Portal/Formulario Público se quedan con capacidad fija por ser contenedores estáticos de bajo costo, y Keycloak se deja fuera a propósito porque escalarlo requeriría configurar clustering de sesiones (JGroups/Infinispan) primero.

### B. Application Load Balancer (ALB) + AWS WAF (El Portero y el Guardaespaldas)
Todo el tráfico de internet golpea primero el ALB por el puerto seguro 443 (HTTPS).
*   **¿Por qué ALB?** Reparte las peticiones equitativamente entre nuestros contenedores. Además, lo configuramos con un "Timeout" enorme (300 segundos) para no cortarle la cara a los usuarios mientras Amazon Bedrock analiza PDFs complejos.
*   **¿Por qué AWS WAF?** Le pusimos un Firewall en frente. Bloquea ataques de hackers (Inyecciones SQL), IPs maliciosas y bots antes de que toquen nuestros servidores. Tu servidor web solo procesa tráfico legítimo.
*   **Límite de tasa global por IP (actualizado 2026-07-30):** El WAF también bloquea a cualquier IP que supere 2000 peticiones en 5 minutos (`RateBasedStatement`). Esto es necesario porque el rate-limiting a nivel de aplicación (`slowapi`, en el backend) mantiene su contador en memoria de cada task de ECS — con 2+ tasks detrás del mismo ALB, un cliente que reparte tráfico entre tasks podía multiplicar su límite real. El WAF ve el tráfico agregado antes de repartirlo, así que aquí el límite sí es global.

### C. Amazon RDS PostgreSQL (La Memoria Incorruptible)
*   **¿Por qué PostgreSQL?** Necesitábamos integridad de datos relacional. Como viste en la estabilización, el sistema es propenso a errores de "doble clic" si dos analistas gestionan un proveedor a la vez. PostgreSQL nos permite usar **Bloqueo Pesimista**, creando una "fila" automática de peticiones que nos asegura que los datos jamás se van a sobreescribir.

### D. Ecosistema AWS Seguro (S3, Secrets Manager y Cloud Map)
*   **Amazon S3:** Guarda los PDFs que suben los proveedores. Es barato y aislado de los servidores web.
*   **Secrets Manager:** Todas las contraseñas (Base de datos, API TusDatos, Zoho Sign) están cifradas aquí. **Por qué:** Cumplimiento de seguridad. Si el código se filtra, los hackers no tendrán ninguna contraseña.
*   **AWS Cloud Map:** Un directorio de red interno. Solo Keycloak se registra en el namespace privado; el backend lo consume mediante `keycloak.sagrilaft-{ambiente}.local`, sin usar el dominio público. Backend, frontend y portal no tienen registros Cloud Map porque el repositorio no identifica consumidores de esos nombres.

---

## 3. Flujo de Integración y Despliegue (Scripts y Docker)

No subimos el código arrastrando carpetas. Automatizamos el proceso mediante la carpeta `/scripts`.

*   **Paso 1 (Docker):** El script `build_and_push_ecr_images.py` empaca el Frontend y el Backend en imágenes de Docker y les pega la estampilla del Commit actual (`git rev-parse HEAD`).
*   **Paso 2 (ECR):** Sube esas imágenes al "repositorio seguro de contenedores" de AWS (Elastic Container Registry). **Actualizado 2026-07-30:** el script valida `.env`, Docker y credenciales AWS antes de empezar, y si falla la construcción de alguna de las 4 imágenes se detiene (fail-fast) e imprime un resumen ✅/❌/⏭ explícito por imagen, dejando claro que no debe continuarse al Paso 3 hasta tener las 4 en ✅. Antes, una falla a mitad de camino dejaba el tag incompleto en ECR sin ningún aviso.
*   **Paso 3 (CDK Deploy):** Se ejecuta el comando de despliegue y AWS baja las nuevas imágenes, enciende los nuevos contenedores, verifica que estén sanos y, cuando comprueba que sirven, apaga los viejos. **Por qué:** Esto se llama *Despliegue Azul/Verde (Rolling Update)*. El portal nunca se cae mientras estamos actualizando el sistema.

---

## 4. Estabilizaciones de Diseño Recientes (Core)

Para garantizar un Go-Live tranquilo, adaptamos la arquitectura con:
1.  **Optimización Bedrock (PDFs):** Instalamos `pypdf` para recortar localmente documentos a un máximo configurable de páginas (`BEDROCK_PDF_MAX_PAGES`, default 7) antes de enviarlos a IA, ahorrando la mitad del tiempo de servidor y reduciendo drásticamente la factura de *Tokens* de Amazon.
2.  **Backoff Exponencial:** Los contenedores están diseñados para reintentar inteligentemente si Zoho Sign o Bedrock no responden a la primera, absorbiendo los fallos de red sin mostrarle pantallas rojas a los usuarios.
3.  **Observabilidad Dual (EMF y Dashboards AWS):** Separamos el monitoreo en dos tableros (Técnico y de Negocio). El backend de Python inyecta logs en formato AWS EMF para medir silenciosamente el costo de IA (Tokens Bedrock), latencia de proveedores (TusDatos, Zoho) y el embudo de aprobaciones, convirtiéndolos automáticamente en gráficas sin costo adicional.
4.  **Límite de tamaño de archivos subidos (2026-07-30):** Antes, el backend leía cualquier archivo subido completo a memoria de una sola vez (`archivo.read()`), sin ningún límite — un solo archivo gigante podía agotar la memoria del proceso sin necesitar volumen de tráfico (DoS de un solo tiro). Ahora el backend lee en bloques de 1 MiB y aborta apenas se supera `MAX_UPLOAD_SIZE_MB` (default 15 MB, configurable por entorno), devolviendo HTTP 413. Se evaluó resolverlo en AWS WAF, pero WAF solo inspecciona hasta 64 KB del cuerpo de la petición — insuficiente para archivos de varios MB — por lo que el control tenía que vivir en la aplicación.
5.  **`FRONTEND_URL` obligatorio y plantillas `.env.example` (2026-07-30):** `load_config()` ahora exige `FRONTEND_URL` en staging/producción (antes caía en silencio a `http://localhost:5173`, arriesgando una configuración de CORS incorrecta sin aviso). Además se crearon `.env.dev.example`, `.env.staging.example` y `.env.prod.example` en la raíz — ya existía `scripts/validate_envs.py` esperándolos (con la lista completa de variables por entorno) pero nunca se habían creado los archivos; los 3 entornos ya pasan la validación (`APROBADO`), y ese script quedó conectado como paso temprano en `.github/workflows/ci.yml`.
6.  **Trazabilidad de versión desplegada (2026-07-30):** antes no había forma rápida de saber, durante un incidente, qué versión exacta corría en un ambiente. `GET /health` y `GET /` ahora responden con `commit` (el `GIT_SHA`, igual al tag de la imagen en ECR — ver `ecs-fargate.ts`), inyectado como variable de entorno desde el mismo `imageTag` que usa el CDK. El registro de versión y notas de release se mantiene en la [guía](../produccion/GUIA_DESPLIEGUE_LOCAL.md#release).

## 5. Diagramas para explicar la solución

Las vistas visuales se mantienen en `diagramas/`. `infraestructura-sagrilaft.puml` y `infraestructura-sagrilaft.drawio` representan el despliegue y sus dependencias; `flujo-producto-sagrilaft.puml` representa el recorrido funcional del expediente. Las diferencias por ambiente (réplicas, modelo de Bedrock y proveedor de listas) se documentan en `docs/arquitectura/DIAGRAMAS_ARQUITECTURA.md`.

## Referencia de recursos, red y permisos

Los identificadores de cuenta, certificado y dominios se mantienen en el
[catálogo por ambiente](../produccion/checklist-valores-staging-prod.md).

### Recursos gestionados por CDK

| Construct | Recurso AWS | Tipo | Propósito |
|-----------|------------|------|-----------|
| `Networking` | VPC `10.0.0.0/16`, subnets públicas/privadas, SGs, NAT de producción y VPC endpoints | VPC | Red privada para ECS/RDS; acceso a servicios AWS por endpoints y salida externa controlada por NAT en producción. |
| `Storage` | Bucket S3 de uploads | S3 | Documentos, PDFs y temporales. Versionado en `prod`. |
| `Secrets` | Secretos por ambiente | Secrets Manager | DB credentials, `SECRET_KEY`, Zoho, SMTP y Keycloak admin. |
| `ConfigParameters` | `/sagrilaft/{env}/config/*` | SSM | Configuracion no sensible e URLs publicas. |
| `Notifications` | SES EmailIdentity + SNS Topic | SES + SNS | Alertas internas al equipo de analistas. |
| `Ecr` | Repos por servicio | ECR | Imagenes Docker privadas para backend, formulario, portal y Keycloak. |
| `Database` | RDS PostgreSQL 16 `db.t3.medium`, una AZ, backups de 7 días | RDS | Base `sagrilaft` usada por backend y Keycloak. La recuperación productiva aún no se ha ensayado; el riesgo está aceptado para el primer corte y P10 sigue abierto. |
| `EcsFargate` | Cluster, task definitions, services, roles, logs, target groups | ECS | Runtime productivo de los cuatro servicios. |
| `LoadBalancer` | ALB + ACM Certificate | ALB + ACM | Enrutamiento HTTPS por hostname/path hacia ECS; el CDK prepara `Strict-Transport-Security: max-age=31536000` en respuestas HTTPS. La verificación productiva sigue pendiente (P08). |

### Arquitectura de Red

```text
Internet
  |
  v
ALB publico (sgAlb: TCP 80/443)
  |-- sagrilaft.dominio.com/      -> ECS formulario-publico:8080
  |-- portal.dominio.com/         -> ECS portal-interno:8080
  |-- auth.dominio.com/           -> ECS keycloak:8080
  |-- /api/* y /health            -> ECS backend:8000

VPC 10.0.0.0/16 - 2 AZs
|-- Subnets publicas
|   `-- ALB
`-- Subnets privadas (aisladas en staging por defecto; con salida NAT en producción)
    |-- ECS Fargate services
    |-- RDS PostgreSQL
    `-- VPC Endpoints: ECR API/Docker, CloudWatch Logs, Secrets Manager, SSM,
        ssmmessages (ECS Exec), SES API/SMTP, S3 Gateway y Bedrock Runtime

NAT Gateway: staging sin NAT por defecto (temporal para pruebas externas);
producción con NAT habilitada en los scripts de despliegue.
```

### Permisos IAM - Roles ECS

| Rol | Permisos principales |
|-----|----------------------|
| Task Execution Role | Pull desde ECR, escritura CloudWatch Logs, lectura Secrets/SSM para inyeccion de runtime. |
| Backend Task Role | S3 read/write, Secrets, SSM, SES, SNS, Bedrock, CloudWatch Metrics y permisos `ssmmessages` de ECS Exec. |
| Frontend/Portal Task Roles | Lectura de parámetros de configuración SSM y permisos `ssmmessages` de ECS Exec. Las variables `VITE_*` se consumen en build time y no se publican como parámetros SSM de runtime. |
| Keycloak Task Role | Lectura de parámetros SSM, credenciales DB y secreto admin Keycloak, además de permisos `ssmmessages` de ECS Exec. |

> Los contenedores ECS no usan access keys estaticas. El SDK AWS obtiene credenciales temporales del Task Role. Los wildcards en Bedrock y SES se mantienen por limitaciones de permisos por recurso en esos servicios. El resto queda restringido por recursos CDK cuando aplica.

### Integración SES y SNS

**Amazon SES** es el canal principal de alertas internas. El backend llama directamente a `boto3 ses.send_email()` con emails `multipart/alternative` (HTML + texto plano). Los templates HTML están versionados en código y se despliegan con la imagen Docker.

**Amazon SNS** existe como canal secundario. El backend puede consultar el topic en health check y publicar alertas si se habilita por configuracion.

`SNS_TOPIC_ARN`, `SES_EMAIL_ORIGEN` y flags de notificacion se inyectan en ECS desde CDK/SSM/Secrets Manager.

### Observabilidad (CloudWatch)

Cada servicio ECS envia stdout/stderr a un Log Group propio:

- `/sagrilaft/{env}/ecs/backend`
- `/sagrilaft/{env}/ecs/frontend`
- `/sagrilaft/{env}/ecs/portal`
- `/sagrilaft/{env}/ecs/keycloak`

ECS deployment circuit breaker queda habilitado con rollback automatico ante fallos de despliegue.

### Repositorios de Contenedores (ECR)

Las imagenes de produccion se almacenan en repositorios ECR privados. El ciclo de vida retiene las ultimas 30 imagenes por repositorio:

| Repositorio | Uso |
|-------------|-----|
| `sagrilaft-prod-backend` | API Python |
| `sagrilaft-prod-formulario-publico` | Frontend publico |
| `sagrilaft-prod-portal-interno` | Portal interno |
| `sagrilaft-prod-keycloak` | Imagen Keycloak productiva |
