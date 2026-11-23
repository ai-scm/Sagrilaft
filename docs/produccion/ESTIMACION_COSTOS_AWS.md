# Costos de SAGRILAFT en AWS: detalle técnico

Cuánto cuesta cada ambiente y por qué, qué configuración produce ese costo, cómo
desplegarla y probarla, y cómo encender y apagar staging. La versión de una página para
la dirección está en `COSTOS_AWS_DIRECCION.md`, que no se versiona: se entrega aparte.

## Dónde estamos

| Ambiente | Configuración en AWS | Costo al mes | Qué falta |
|---|---|---|---|
| Staging | La nueva, desplegada y probada el 17-nov-2026 | ~84 USD estimado (apagado salvo unas 40 h de pruebas) | Confirmarlo con la factura de diciembre |
| Producción | La nueva, desplegada el 18-nov-2026. Backend con 2 GB desde el 23-nov-2026 | ~175 USD estimado (la anterior costaba ~327 USD según factura) | Confirmarlo con la factura de diciembre |
| **Total** | | **~259 USD** | |

Las cifras de la configuración nueva son estimaciones con precios de lista. Pasan a ser
firmes cuando las confirme una factura completa. La de noviembre mezcla las dos
configuraciones, así que la primera que sirve para comparar es la de diciembre.

Precios de lista en `us-east-1`, sin impuestos. Un mes son 730 horas.

## De dónde salen las cifras de la configuración anterior

- **Con etiqueta `Project=sagrilaft` en Cost Explorer:** red, base de datos, NAT,
  balanceador, WAF, CloudWatch, secretos y ECR. Se tomó lo cobrado del 1 al 16 de
  noviembre de 2026 y se llevó a 730 horas.
- **Calculadas a partir de los recursos en ejecución:**
  - Fargate, porque hasta ahora las tareas no heredaban las etiquetas: 4 servicios con
    una copia en cada ambiente.
  - Las IPs públicas.
  - Bedrock, con la métrica propia `Sagrilaft/Negocio`.

### Producción antes del 18-nov: ~327 USD

| Servicio | USD al mes |
|---|---|
| VPC endpoints de interfaz (9 servicios × 2 zonas) | 131,5 |
| RDS PostgreSQL `db.t3.medium`, 100 GB gp2 | 64,2 |
| ECS Fargate (4 servicios, 1 copia) | 54,1 |
| NAT Gateway | 32,9 |
| Application Load Balancer | 16,5 |
| IPs públicas (ALB y NAT) | 11,0 |
| WAF | 9,1 |
| CloudWatch | 5,7 |
| Secrets Manager, ECR, S3, Bedrock, SES, SNS | ~2 |

Los endpoints de interfaz son el gasto más grande y no hacen falta: producción ya tiene
NAT, que da la misma salida hacia AWS. Pagar los dos es pagar dos caminos al mismo
lugar.

### Staging antes del 17-nov: ~291 USD

| Servicio | USD al mes |
|---|---|
| VPC endpoints de interfaz (9 servicios × 2 zonas) | 131,5 |
| RDS PostgreSQL `db.t3.medium`, 100 GB gp2 | 64,2 |
| ECS Fargate (4 servicios, 1 copia, 24 horas) | 54,1 |
| Application Load Balancer | 16,4 |
| WAF | 9,1 |
| IPs públicas (ALB) | 7,3 |
| CloudWatch, Secrets Manager, ECR, S3 | 8,2 |

## Configuración nueva

### Producción: ~175 USD

| Servicio | Configuración | USD al mes |
|---|---|---|
| ECS Fargate | Backend (0,5 vCPU, 2 GB), Keycloak (0,5 vCPU, 1 GB), formulario y portal (0,25 vCPU, 0,5 GB), con una copia cada uno. El backend escala de 1 a 2 copias (CPU 60%, memoria 70%) | 57 |
| RDS PostgreSQL | `db.t3.small`, una zona, 100 GB, copias de seguridad de 14 días | 38 |
| NAT Gateway | Un NAT, con salida a internet y a las APIs de AWS | 33 |
| ALB e IPs públicas | HTTPS por dominio hacia los cuatro servicios | 28 |
| WAF | Reglas administradas de AWS, límite por IP y regla para la consola de Keycloak | 9 |
| CloudWatch, secretos, ECR, S3, SES, SNS, Cloud Map, Bedrock | | 10 |

Lo que puede variar según el uso:
- **Segunda copia del backend:** se enciende sola con carga alta. Hasta 21 USD al mes si
  estuviera encendida todo el mes.
- **Trabajador de listas:** 0 mientras las listas estén deshabilitadas; 9 USD al mes al
  activarlas.
- **Bedrock:** unos 0,004 USD por documento leído.

### Staging: ~84 USD con unas 40 horas de uso

| Concepto | USD |
|---|---|
| Fijo, también con todo apagado: NAT e IP (37), ALB e IPs (24), WAF (9), disco RDS de 20 GB gp3 (2,3), CloudWatch, secretos y lo demás (6) | ~79 al mes |
| Por hora encendido: Fargate con 4 servicios y el trabajador de listas simuladas (0,09) y RDS `db.t4g.small` (0,03) | ~0,12 por hora |

Lo fijo se cobra por existir, no por usarse. Se apagan Fargate y la instancia de RDS,
que se cobran por hora encendidos. El NAT, el ALB y el WAF se dejan: borrarlos y
crearlos de nuevo exige un `cdk deploy` cada vez, y cambian el DNS y la IP de salida.

## Arquitectura que sostiene estos costos

Resumen de lo que determina el costo. La arquitectura completa está en
[Arquitectura en AWS](../arquitectura/DOCUMENTACION_ARQUITECTURA.md).

- **Red:**
  - Las tareas ECS están en subredes privadas y salen por el NAT Gateway. Por ahí van
    Zoho Sign, Tusdatos y las APIs de AWS (ECR, CloudWatch Logs, Secrets Manager, SSM,
    ECS Exec, SES por API y por SMTP, y Bedrock), con TLS.
  - S3 va por un endpoint gateway gratuito, que no pasa por el NAT ni se cobra por GB.
  - Los 9 endpoints de interfaz solo se crean si un ambiente se despliega sin NAT
    (`habilitarNatEgress=false`). En ese caso son la única ruta hacia AWS.
  - Cada ambiente tiene su propia VPC y su propio NAT; no se comparten. Las dos VPC
    usan el mismo rango `10.0.0.0/16`, así que tampoco se podrían conectar entre sí.
  - Código: [networking.ts](../../infra/sagrilaft/lib/constructs/networking.ts).
- **Base de datos:**
  - `db.t3.small` en producción y `db.t4g.small` en staging y dev, las dos con 2 GB de
    memoria.
  - Disco: 100 GB gp2 en producción. En staging y dev, 20 GB gp3 (el mínimo de RDS),
    con crecimiento automático hasta 50 GB.
  - Carga medida del 3 al 16 de noviembre de 2026: CPU promedio del 4% (picos del
    62–65%), unos 0,9 GB de memoria usados, 11 conexiones como máximo y menos de 1 GB
    de datos. Por eso 2 GB alcanzan.
  - Código: [database.ts](../../infra/sagrilaft/lib/constructs/database.ts).
- **Capacidad** ([sagrilaft-stack.ts](../../infra/sagrilaft/lib/sagrilaft-stack.ts)):
  - Una copia por servicio por defecto (`desiredCount=1`).
  - Backend de 1 a 2 copias (`backendMaxCapacity=2`). El número de copias lo decide
    el autoescalado: la plantilla no lo fija, para que un despliegue no apague la
    segunda copia.
  - Tamaño de cada tarea ([ecs-fargate.ts](../../infra/sagrilaft/lib/constructs/ecs-fargate.ts)):
    backend 0,5 vCPU y 2 GB; Keycloak y migraciones 0,5 vCPU y 1 GB; formulario,
    portal y trabajador de listas 0,25 vCPU y 0,5 GB.
  - Por qué el backend tiene 2 GB (23-nov-2026): con 1 GB, sus 4 workers ocupaban
    ~62% en reposo, y cada documento que se sube (hasta 15 MB) se lee completo a
    memoria y se envía a Bedrock en la misma petición. Unas pocas subidas grandes
    simultáneas podían agotar la memoria y reiniciar la copia entera. El GB extra
    cuesta ~3,2 USD al mes por copia; una segunda copia entera, ~21 USD.
  - Trabajador de listas en 0 si `proveedorListasCautela=deshabilitado`.
- **Etiquetas:**
  - Todo lo que crea CDK lleva `Project=sagrilaft`, `Environment`, `Component` y
    `ManagedBy`; lo que vive fuera de CDK se etiqueta con un script
    ([ETIQUETADO_AWS.md](configuracion/ETIQUETADO_AWS.md)). Las cuatro claves ya están
    activas en Cost Explorer, así que se puede filtrar el costo por componente.
  - Las tareas de Fargate las heredan del servicio (`propagateTags: SERVICE` en
    [ecs-fargate.ts](../../infra/sagrilaft/lib/constructs/ecs-fargate.ts)).
- **Pruebas:** [costos-minimos.test.ts](../../infra/sagrilaft/test/costos-minimos.test.ts)
  verifica todo lo anterior.

## Despliegue y pruebas

El cambio sale de la rama `feature/listas-seleccion-unica-adaptador`. Esa rama trae,
además de los cambios de costo, el módulo de listas: el trabajador, el secreto y los
parámetros de Tusdatos, y permisos IAM. Los dos van juntos porque los cambios de costo
dependen del trabajador de listas.

Las imágenes del release deben estar en ECR con el SHA del commit que se despliega.

### Staging: hecho el 17-nov-2026

Staging se desplegó con una base nueva y vacía de 20 GB. RDS no permite achicar un
disco, así que el despliegue creó la base nueva y dejó la anterior fuera de la pila
(`RETAIN`). Después de las pruebas, la anterior se borró junto con su grupo de
subredes.

Resultado:
- El diff solo mostró lo esperado: salen los 9 endpoints y su grupo de seguridad, se
  crean el NAT, la base nueva y el módulo de listas, y no se reemplaza ningún servicio
  ni subred.
- El release en modo `bootstrap` creó las tablas (Alembic, revisión `n54c67d890eb`) y
  encendió los cinco servicios. El smoke de solo lectura pasó 12 de 12.
- Pasaron todas las pruebas de la tabla de abajo.

Si hubiera que repetirlo (por ejemplo, para recrear staging desde cero):

1. **Comparar con lo desplegado:** `npm run diff:staging`, y también el diff con los
   argumentos de `deploy:staging:bootstrap`, que es lo que se va a aplicar. No debe
   aparecer el reemplazo de ningún servicio ni subred.
2. **Desplegar la infraestructura con los programas en 0:**
   `npm run deploy:staging:bootstrap`. Tardó unos 13 minutos, casi todo por la base.
3. **Preparar la base y arrancar los programas** con el release en modo `bootstrap`:
   - en el plan: `"mode": "bootstrap"`, `"previous_tag": "bootstrap-placeholder"`,
     `"previous_revisions": []`, `"desired_count": 1`;
   - en el contexto: `"habilitarNatEgress": true`, `"backendMaxCapacity": 2`,
     `"proveedorListasCautela": "dummy"` y `"zohoSecretYaExiste": false`.
4. **Configurar Keycloak a mano.** Con una base vacía, Keycloak crea los realms desde
   `keycloak/realm-sagrilaft.json` y el administrador desde el secreto
   `keycloak_admin`. Ese archivo no trae ni la protección contra fuerza bruta ni los
   usuarios:
   - **Fuerza bruta**, en los realms `master` y `sagrilaft` (Realm settings → Security
     defenses → Brute force detection): bloqueo temporal, 5 fallos, espera de 1
     minuto con tope de 15 y reinicio a las 12 horas.
   - **Usuarios**, en el realm `sagrilaft`, con roles del realm asignados directo al
     usuario: `acceso_clientes`, `acceso_proveedores` y, para listas, `listas_revisor`
     o `listas_operador`. El backend lee los roles del token; un grupo sin roles
     asignados no da ningún permiso.
   - La consola de Keycloak avisa que el administrador es "temporal". Es el
     administrador de arranque que crea Keycloak 26. Se deja como está: es el usuario
     del secreto `keycloak_admin`, y lo usa `scripts/listas/crear_roles_listas_keycloak.sh`.
5. **Probar** (tabla de pruebas, columna staging).
6. **Apagar staging:** `scripts/aws/staging_encendido.sh apagar`.

### Producción: hecho el 18-nov-2026

Producción conservó su base de datos y sus datos, con el disco de 100 GB.

- **Infraestructura (18-nov):** `cdk deploy` quitó los 9 endpoints de interfaz, creó el
  trabajador de listas en 0 copias y dejó el autoescalado del backend en 1 a 2 copias
  (registro en `tmp/despliegue-prod-20261118/deploy_prod_infra.log`).
- **Release `d4cdb84` (18-nov):** terminó bien, con la migración del módulo de listas.
- **Verificado el 2026-11-23:** la base de datos es `db.t3.small` con 14 días de copias
  y el backend tiene 2 GB de memoria.
- **Pendiente:** confirmar en Cost Explorer que Fargate aparece con `Project=sagrilaft` y,
  al cerrar diciembre, comparar la factura con lo estimado.

| Prueba | Qué valida | Staging (17-nov) | Producción |
|---|---|---|---|
| Las tareas arrancan y `/health` responde | Descarga de imágenes, secretos y SSM por el NAT | Pasó | Pasó (comprobado el 23-nov) |
| Registros en CloudWatch | Logs por el NAT | Pasó | Pasó (comprobado el 23-nov) |
| Inicio de sesión en el portal con OTP | Keycloak y su base de datos | Pasó | Por hacer |
| Subir y descargar documentos | S3 por el endpoint gateway | Pasó | Por hacer, con un expediente de prueba |
| Lectura de un documento con IA | Bedrock por el NAT | Pasó | Por hacer, un documento |
| Crear un acceso y recibir el correo | SES por SMTP a través del NAT | Pasó | Por hacer, a un correo interno |
| Firma completa en Zoho Sign: envío, webhook, «firmado» y descarga | Salida a internet y entrada del webhook | Pasó | Solo con autorización; el webhook de producción no se ha probado (P05) |
| Expediente completo: crear, devolver, corregir, firmar y cerrar | Flujo completo sobre la base | Pasó | No |
| Consulta de listas simulada, informe y revisión humana | Trabajador de listas y custodia en S3 | Pasó | No aplica (listas deshabilitadas) |
| Bloqueo tras 5 intentos fallidos de inicio de sesión | Protección contra fuerza bruta | Pasó | Por hacer |
| Usuario con un solo tipo de contraparte | Filtro por rol | Pasó | No |
| `staging_encendido.sh apagar`, `estado` y `encender` | Procedimiento de encendido | Pasó | No aplica |

Las pruebas de producción que faltan son parte de la prueba completa de producción ([P07](PENDIENTES_PRODUCCION.md#p07)).

## Encender y apagar staging

```bash
scripts/aws/staging_encendido.sh estado     # muestra programas y base (no cambia nada)
scripts/aws/staging_encendido.sh apagar     # todo a 0 y base detenida (menos de 1 minuto)
scripts/aws/staging_encendido.sh encender   # base y programas arriba y sanos (unos 10 minutos)
```

- **`apagar`:**
  1. Baja a 0 el autoescalado del backend. Si no se baja, AWS vuelve a crear la tarea.
  2. Pone todos los servicios en 0 y espera a que se detengan.
  3. Detiene la instancia de RDS.
- **`encender`:**
  1. Arranca RDS y espera a que esté disponible (unos 5 minutos).
  2. Pone todos los servicios en 1 y restaura el autoescalado del backend a 1–2.
  3. Espera a que el balanceador vea sanos todos los servicios. Keycloak es el último:
     tarda 2 o 3 minutos más que el resto y, mientras arranca, su dominio responde
     502.
- **Alcance:** solo actúa sobre el clúster `sagrilaft-staging` y la base que pertenece a
  su pila.

Precauciones:

1. AWS reinicia sola una instancia RDS detenida a los 7 días. Si pasa, hay que volver a
   ejecutar `apagar`.
2. CloudFormation no puede modificar una RDS detenida. Hay que encender antes de
   cualquier `cdk deploy` o release.
3. Un despliegue deja los servicios en 1. Hay que apagar al terminar.
4. Al apagar, Keycloak registra errores de conexión a la base mientras se detiene. Son
   normales.

## Etiquetas y seguimiento en Cost Explorer

Para ver el gasto: filtrar por `Project=sagrilaft` y agrupar por `Environment` y por
servicio. La cuenta la comparten otros proyectos; sin ese filtro, se ve el gasto de
todos.

**Recursos creados fuera de CDK que llevan las etiquetas puestas a mano:**
- el secreto `sagrilaft/prod/zoho_credentials`;
- los usuarios IAM de SMTP (`sagrilaft-ses-smtpp` no tiene uso confirmado y solo lleva
  `Project`);
- los grupos de registros de Container Insights;
- las zonas DNS privadas de Cloud Map.

Lo que se cree a mano para SAGRILAFT debe llevar las mismas dos etiquetas.

**Lo que no aparece con la etiqueta:**
- **IPs públicas del ALB:** AWS no permite etiquetarlas; unos 7 USD por ambiente.
- **Bedrock:** sin etiqueta por llamada; el consumo se ve en `BedrockInputTokens` del
  tablero de negocio.
- **Certificado `*.ia.blend360.com` y zona `ia.blend360.com`:** son compartidos.

## Más ahorros posibles

Con la configuración nueva, lo que queda por recortar es poco. Esto es lo que hay y lo
que costaría:

| Opción | Ahorro | A cambio | Recomendación |
|---|---|---|---|
| Savings Plan de Fargate e instancia reservada de RDS en producción | ~15 USD al mes | Compromiso de un año | Sí, cuando 2 o 3 facturas confirmen el tamaño |
| Formulario y portal como sitio estático (S3 + CloudFront) | ~16 USD al mes en producción | Cambiar cómo se publican las dos aplicaciones | Solo si algún día se rehace esa parte |
| RDS de producción `db.t4g.small` | ~3 USD al mes | Un reinicio de unos minutos | No compensa |
| Fargate Spot en staging | ~0,06 USD por hora encendido | AWS puede detener una tarea con 2 minutos de aviso | No: puede cortar pruebas |

El piso de cada ambiente es el ALB, el WAF y las IPs, unos 35 USD: es lo mínimo para
publicar con HTTPS y protección. Bajar de ahí exige quitar seguridad o el NAT, y eso no
se recomienda.
