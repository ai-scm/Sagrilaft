# Arquitectura en AWS

Cómo está montado SAGRILAFT en AWS, por qué se eligió cada pieza y qué permisos
tiene cada parte. Cómo funciona la aplicación por dentro (estados del expediente,
firma, auditoría) está en [Arquitectura de la aplicación](ARQUITECTURA_CORE.md). Qué
versión corre hoy en cada ambiente está en [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).

Revisado el 2026-11-23 contra el código de infraestructura (`infra/sagrilaft/lib`) y,
en lo que se indica, contra AWS. Las razones de diseño vienen de la documentación
anterior. Si este documento y el código no coinciden, manda el código.

## En una frase

SAGRILAFT corre en contenedores administrados por AWS (no hay servidores propios
que mantener), detrás de un balanceador con cortafuegos, con una base de datos
PostgreSQL, y toda la infraestructura está escrita como código (CDK), de modo que
se puede revisar y volver a crear igual.

## Las piezas

### Contenedores (ECS Fargate)

Hay cinco servicios. AWS los arranca, los vigila y reemplaza el que falle.

| Servicio | Qué hace | Copias |
|---|---|---|
| Backend (FastAPI) | La API: formularios, documentos, IA, firma y correos | 1 a 2: se añade una segunda copia sola si la CPU pasa del 60 % o la memoria del 70 % |
| Formulario público | La página que llena la contraparte | 1 |
| Portal interno | La aplicación del equipo interno | 1 |
| Keycloak | Inicio de sesión del equipo interno | 1. No escala: tener varias copias exigiría configurar que compartan sesiones |
| Trabajador de listas | Procesa las consultas a listas cautelares | 0 mientras las listas estén deshabilitadas (producción); 1 si están activas |

Hay además una tarea de **migración**, que no es un servicio: se lanza en cada
release para actualizar la base de datos y termina.

Al desplegar una versión nueva, AWS arranca las copias nuevas, comprueba que estén
sanas y solo entonces apaga las viejas. Si las nuevas no arrancan, vuelve solo a la
versión anterior (circuit breaker).

### Balanceador (ALB) y cortafuegos (WAF)

Todo el tráfico entra por HTTPS al balanceador, que lo reparte según el dominio
(los nombres de cada ambiente están en [Configuración en AWS](../produccion/configuracion/MATRIZ_AWS_CONFIG.md#datos-de-la-cuenta)):

| Dominio | Va a |
|---|---|
| Formulario público | El formulario; lo que empieza por `/api` va al backend |
| Portal interno | El portal |
| Inicio de sesión | Keycloak |

- **Espera de hasta 300 segundos** por respuesta, porque leer documentos con IA puede tardar.
- **Fuerza HTTPS** (HSTS de un año). Verificado en producción el 2026-10-21 ([P08](../produccion/PENDIENTES_PRODUCCION.md#p08)).
- **Registros de acceso:** cada visita queda guardada 90 días en un bucket propio, con la
  IP real del visitante (comprobado en staging y producción el 2026-11-23).
- **El cortafuegos** bloquea ataques comunes con reglas administradas por AWS y,
  además, cualquier IP que pase de 2.000 peticiones en 5 minutos, o de 200 en 5
  minutos contra la consola de administración de Keycloak. El límite general vive en
  el cortafuegos porque el backend cuenta los intentos en la memoria de cada copia:
  solo el cortafuegos ve el total.

### Base de datos (RDS PostgreSQL 16)

Una sola base, `sagrilaft`, para la aplicación y para Keycloak. Se eligió PostgreSQL
porque permite bloquear un expediente mientras alguien lo modifica: así dos personas
no se pisan los cambios.

| | Producción | Staging |
|---|---|---|
| Tamaño | `db.t3.small`, 100 GB | `db.t4g.small`, 20 GB (crece hasta 50) |
| Zonas | Una | Una |

Copias de seguridad (cuántos días se guardan y cuándo se toma una manual): ver la
[estrategia de respaldos del runbook](../operacion/RUNBOOK_OPERATIVO.md#restauracion).

Cifrada, no accesible desde internet y protegida contra borrado. Estar en una sola
zona y no haber ensayado la restauración en producción son riesgos aceptados
([P02](../produccion/despliegue/P02_GO_NO_GO_ROLLBACK.md), [P10](../produccion/PENDIENTES_PRODUCCION.md#p10)).

### Archivos, secretos y configuración

- **S3:** guarda los documentos que suben las contrapartes, los PDF y los informes de
  listas. En producción guarda versiones anteriores de cada archivo.
- **Secrets Manager:** contraseñas y llaves. **Parameter Store (SSM):** configuración no
  secreta. Detalle en [Configuración en AWS](../produccion/configuracion/MATRIZ_AWS_CONFIG.md).
- **Imágenes (ECR):** un repositorio por servicio (`sagrilaft-<ambiente>-backend`,
  `-formulario-publico`, `-portal-interno` y `-keycloak`; el trabajador de listas usa la
  imagen del backend). Cada versión se guarda con el identificador de su commit, no se
  puede sobrescribir y se conservan las últimas 30.

### Red

```text
Internet
  |
  v
Balanceador (subredes públicas) ── cortafuegos
  |
  v
Subredes privadas (2 zonas, red 10.0.0.0/16)
  ├── los cinco servicios y la tarea de migración
  ├── la base de datos
  └── salida:
        ├── a S3 por un acceso privado gratuito (endpoint gateway)
        └── a internet y a las demás APIs de AWS por un NAT
```

El NAT está encendido en los dos ambientes: es la salida hacia Zoho Sign, Tusdatos,
Bedrock, SES y las demás APIs de AWS. Había además nueve accesos privados de pago a
servicios de AWS; se quitaron en staging el 17-nov-2026 y en producción el 18-nov-2026
porque hacían lo mismo que el NAT ([costos](../produccion/ESTIMACION_COSTOS_AWS.md)). El código solo los crea si un
ambiente se despliega sin NAT.

Keycloak tiene además un nombre interno (`keycloak.sagrilaft-<ambiente>.local`, con
Cloud Map) para que el backend lo consulte sin salir a internet.

### Correo y avisos

- **SES** envía los correos a las contrapartes y los avisos internos (en HTML y texto plano;
  las plantillas están en el código).
- **SNS** reparte los avisos de las alarmas por correo. Solo en producción: en
  staging las alarmas existen pero no avisan.
- **Alarmas:** 16, definidas en `observabilidad-alarmas.ts`. La lista y qué hacer con cada
  una están en el [runbook](../operacion/RUNBOOK_OPERATIVO.md#que-hacer-alarma).
- **Tableros:** uno técnico y uno de negocio en CloudWatch (`dashboard-tecnico.ts` y
  `dashboard-negocio.ts`). El backend escribe métricas de negocio en sus registros con
  formato EMF (espacio `Sagrilaft/Negocio`). Qué muestra cada gráfico no se revisó en esta
  actualización.

### Registros (CloudWatch Logs)

Cada servicio escribe en `/sagrilaft/<ambiente>/ecs/<servicio>`. Backend, trabajador
de listas y migración los guardan 30 días; Keycloak, formulario y portal, 14.

## Permisos de cada servicio

Ningún contenedor tiene llaves fijas: cada uno recibe permisos temporales de su rol. Los
cinco servicios tienen activada la consola remota (ECS Exec; verificado en producción el
2026-11-23), y CDK da a cada rol el permiso que esta necesita.

| Rol | Puede |
|---|---|
| Ejecución (común) | Descargar imágenes, escribir registros y leer los secretos y parámetros que necesita al arrancar |
| Backend (y la tarea de migración, que usa el mismo rol) | Leer y escribir en el bucket, leer sus secretos y parámetros, enviar correos (SES), publicar en SNS, usar Bedrock y escribir métricas |
| Trabajador de listas | Solo leer y escribir los informes de listas (`listas/custodia/` del bucket) |
| Formulario y portal | Leer su configuración |
| Keycloak | Leer su configuración, la contraseña de la base y el secreto de administrador |

Bedrock y SES usan permisos sin restringir a un recurso concreto porque esos
servicios no lo permiten bien; el resto se limita a los recursos de SAGRILAFT.

## Cómo llega una versión nueva

1. Se construyen las cuatro imágenes con el identificador del commit y se suben a ECR.
2. El script de releases actualiza la base de datos (si hace falta) y después los servicios.
3. `GET /health` responde con el commit que está corriendo.

Paso a paso: [guía de despliegue](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md).

## Decisiones de diseño que siguen vigentes

- **Leer menos páginas con IA:** cada PDF se recorta a 7 páginas antes de enviarlo a
  Bedrock; ahorra tiempo y costo.
- **Reintentos con espera creciente** cuando Zoho o Bedrock no responden a la primera.
- **Tamaño máximo de archivo (15 MB):** el backend lee los archivos por partes y corta
  apenas se pasa del límite. No se hace en el cortafuegos porque este solo revisa los
  primeros 64 KB de cada petición.
- **`FRONTEND_URL` obligatorio** en staging y producción, para no abrir CORS por error.

## Diagramas

Las fuentes editables están en `diagramas/` (en la raíz del repositorio):

- `infraestructura-sagrilaft.puml` y `.drawio`: dónde corre cada pieza en AWS y cómo se conecta.
- `flujo-producto-sagrilaft.puml`: el recorrido del expediente, desde el formulario hasta la firma y el cierre.

Al dibujar o presentar: el modelo de IA es «el configurado en el ambiente»; las listas
cautelares son opcionales (simuladas en staging, deshabilitadas en producción); Zoho
habla en los dos sentidos (el backend lo llama y Zoho avisa al webhook
`/api/webhooks/zoho-sign`, protegido con firma HMAC). No hay guía de presentación
([detalle](../evidencia/README.md#guia-presentacion)). Si un diagrama no coincide con el
código, se corrige el diagrama. Los diagramas no se revisaron contra el código en esta
actualización.
