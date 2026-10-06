# Pruebas De Integracion - SAGRILAFT

Este documento explica como esta construido el harness de integracion, que valida
y cómo ejecutarla. Las tareas de ampliación se siguen en [P19](../../docs/produccion/PENDIENTES_PRODUCCION.md#p19).

## Objetivo

Las pruebas de integracion buscan validar que las piezas principales del backend
trabajen juntas:

- API FastAPI;
- schemas de entrada/salida;
- inyeccion de dependencias;
- servicios de aplicacion;
- repositorios SQLAlchemy;
- modelos de persistencia;
- storage local;
- maquina de estados;
- auditoria, alertas y notificaciones mediante dobles controlados.

La intencion no es probar AWS, Zoho, Keycloak o correo real. Esos sistemas se
reemplazan por dobles en memoria para que la suite sea rapida, deterministica y
ejecutable en local/CI sin credenciales externas.

## Ubicacion

- Harness: `tests/integration/conftest.py`
- Smoke test inicial: `tests/integration/test_harness_integracion.py`
- Marcador pytest: `pytest.ini`

Comando principal:

```bash
venv/bin/pytest tests/integration -q
```

Comando de suite completa:

```bash
venv/bin/pytest -q
```

Nota: en el sandbox de Codex fue necesario ejecutar pytest con permisos elevados
porque el entorno bloquea abrir sockets locales. El harness levanta Uvicorn en
`127.0.0.1` con un puerto efimero. En una maquina local normal o CI esto no
deberia requerir permisos especiales.

## Como Esta Hecho El Harness

El harness prepara una aplicacion real de SAGRILAFT, pero controla sus bordes
externos.

### 1. Entorno de integracion

Antes de importar la app se definen variables minimas:

- `APP_ENV=test`
- `DATABASE_URL=postgresql+psycopg://...`
- `SECRET_KEY=test-secret-key`
- `FRONTEND_URL=http://frontend.test`
- `PORTAL_INTERNO_URL=http://portal.test`
- `STORAGE_BACKEND=local`
- `ZOHO_*` con valores de prueba
- `PROVEEDOR_LISTAS_CAUTELA=dummy`
- `SES_NOTIFICACIONES_ENABLED=false`
- `SNS_NOTIFICACIONES_ENABLED=false`
- `PORTAL_AUTH_DISABLED=true`
- `AWS_EC2_METADATA_DISABLED=true`

La URL PostgreSQL inicial existe solo para permitir importar el modulo global de
persistencia, que crea un engine al cargar. La base usada realmente por cada
test se inyecta despues mediante override de `get_db`.

El harness guarda el entorno original y lo restaura al finalizar para que otras
suites no dependan accidentalmente de estas variables.

### 2. Base de datos aislada

Cada prueba recibe una sesion SQLAlchemy sobre SQLite en memoria:

- se crea un engine por test;
- se ejecuta `Base.metadata.create_all(engine)`;
- se entrega una sesion SQLAlchemy;
- al final se cierra la sesion, se eliminan las tablas y se destruye el engine.

Esto permite probar repositorios y modelos reales sin tocar bases locales ni RDS.

SQLite no replica todos los comportamientos de PostgreSQL. La variante
PostgreSQL ya existe en el harness mediante `TEST_DATABASE_ADMIN_URL` o
`TEST_DATABASE_URL`. El 2026-10-01 se registraron 12/12 pruebas del flujo en
ambas bases y 2/2 de migraciones. Ver [evidencia y alcance](../../docs/evidencia/e2e-staging/VALIDACION_STAGING_E2E.md).
Esto no acredita toda la suite sobre PostgreSQL ni su ejecución en CI.

### 3. API HTTP real

El fixture `cliente_api` levanta la app con Uvicorn en `127.0.0.1` y un puerto
libre. Luego usa `httpx.Client` para llamar endpoints reales.

Se usa este enfoque porque en este entorno `fastapi.testclient.TestClient` y
`httpx.ASGITransport` quedaron bloqueados incluso con una FastAPI minima. Uvicorn
por loopback evita esa incompatibilidad y se parece mas al modo real de ejecucion.

El servidor se levanta con `lifespan="off"` porque el harness instala
explicitamente `app.state` con config, storage y dobles. Asi evitamos inicializar
clientes reales de Bedrock, Zoho o notificaciones.

El fixture limpia los contadores del rate limiter antes y despues de cada prueba.
Esto mantiene la suite deterministica: varias pruebas pueden llamar endpoints
sensibles desde `127.0.0.1` sin que una prueba herede los intentos de otra.

### 4. Overrides de dependencias

El harness sobreescribe:

- `get_db`: entrega la sesion de prueba.
- `portal_interno`: entrega un usuario autenticado de prueba.
- `obtener_servicio_email`: entrega un notificador en memoria.

El usuario de prueba tiene roles:

- `acceso_clientes`
- `acceso_proveedores`

Esto permite probar endpoints protegidos del portal interno sin depender de
Keycloak/JWKS.

### 5. Dobles en memoria

Los dobles capturan efectos secundarios para que los tests puedan hacer
aserciones de negocio.

#### `NotificadorEnMemoria`

Reemplaza correo transaccional a contraparte. Guarda llamadas en:

- `accesos_creados`
- `devoluciones`
- `rechazos`
- `actualizaciones_reabiertas`

#### `AlertasPortalEnMemoria`

Reemplaza alertas internas del portal. Guarda eventos en `eventos` y expone
`metricas()` con conteo de enviadas/fallidas.

#### `ExtractorIAEnMemoria`

Reemplaza Bedrock. Por defecto retorna una extraccion no ejecutada:

```python
ResultadoExtraccion(
    extraido=False,
    mensaje="Extraccion IA omitida en pruebas de integracion.",
)
```

Tambien guarda cada solicitud recibida para validar que un documento disparo o
no disparo analisis IA.

#### `ZohoSignEnMemoria`

Reemplaza Zoho Sign. Permite simular:

- creacion de solicitud de firma;
- descarga de documento firmado;
- cancelacion de solicitud;
- consulta de estado actual.

Por defecto el estado simulado es `Completed`.

#### `OrquestadorEnMemoria`

Expone el extractor fake bajo la misma forma esperada por la aplicacion:

```python
orquestador.extractor
```

## Tipos De Test De Integracion Implementados Hoy

Actualmente existen diecinueve grupos de pruebas de integracion:

### 1. Smoke test del harness

`test_harness_expone_api_real_con_dependencias_controladas`

Este test valida que:

- el servidor HTTP real responde `GET /health`;
- la respuesta de salud es `200`;
- el cuerpo indica `status=healthy`;
- el storage local temporal esta disponible;
- el adaptador de alertas en memoria esta instalado y sin eventos iniciales.

Este test no pretende cubrir un flujo SAGRILAFT completo. Su funcion es confirmar
que el laboratorio de integracion arranca y que los dobles principales estan
conectados.

### 2. Contrato de correo obligatorio en acceso manual

`test_acceso_manual_correo_obligatorio.py`

Estos tests validan el contrato de entrada del flujo principal:

- crear acceso manual sin `correo_destinatario` responde `422`;
- crear acceso manual con correo invalido responde `422`;
- crear acceso manual con correo valido responde `201`;
- la respuesta incluye credenciales de acceso: `formulario_id`,
  `codigo_peticion`, `pin`, `token_diligenciamiento` y
  `enlace_diligenciamiento`;
- `correo_enviado` queda en `true` usando `NotificadorEnMemoria`;
- el doble de correo registra exactamente una notificacion de acceso creado.

Esto confirma que el backend ya no permite crear accesos manuales nuevos sin
correo destinatario. Los endpoints de consulta/actualizacion de correo por token
quedan fuera del flujo principal y se consideran compatibilidad para accesos
historicos.

### 3. Flujo principal de diligenciamiento

`test_flujo_principal_diligenciamiento.py`

Este test valida el primer camino funcional completo del proyecto:

- el portal interno crea un acceso manual con correo obligatorio;
- el destinatario externo entra por el link de diligenciamiento usando
  `token_diligenciamiento`;
- el ingreso por link no pide codigo ni PIN;
- el formulario queda en estado `borrador`;
- el backend acepta autoguardado remoto con `PUT /api/formularios/{id}`;
- si el destinatario necesita retomar sesion, usa `codigo_peticion` + `pin`;
- la recuperacion devuelve el mismo formulario con los datos autoguardados.

Este test todavia no radica el formulario. El envio final requiere completar
campos obligatorios del negocio y se cubre en una prueba separada.

### 4. Credenciales invalidas y accesos no vigentes

`test_acceso_manual_credenciales_invalidas.py`

Estos tests validan los rechazos del acceso externo sin mezclar reglas de
completitud del formulario:

- un token inexistente no resuelve ningun formulario y retorna `404`;
- un codigo de peticion inexistente no recupera sesion y retorna `401`;
- un PIN incorrecto no recupera sesion y retorna `401`;
- un token incorrecto no autoriza el envio final y retorna `401`;
- un acceso expirado bloquea tanto el link de diligenciamiento como la
  recuperacion por codigo + PIN, ambos con `410`.

La intencion es proteger la frontera de seguridad del flujo externo: el backend
no debe revelar si fallo el codigo o el PIN, y debe diferenciar entre enlace
inexistente, credenciales incorrectas y acceso vencido.

### 5. Formulario minimo y validacion de completitud

`test_formulario_minimo_validacion.py`

Estos tests empiezan a aislar las reglas de radicacion sin mezclar todavia
documentos, PDF ni storage definitivo:

- un formulario creado por acceso manual no puede enviarse incompleto;
- el backend responde `valido=false` con errores de campos obligatorios;
- un intento de envio invalido no consume el token de diligenciamiento;
- el payload minimo de persona juridica se puede autoguardar;
- la recuperacion con codigo de peticion + PIN devuelve ese mismo payload
  autoguardado;
- los valores de enums usados por el test son los valores reales del proyecto,
  incluyendo tildes cuando el contrato las exige.

El payload minimo vive en `tests/integration/soporte/formularios.py`. No intenta
representar todos los casos del formulario; solo cubre la ruta juridica base que
el validador de envio exige hoy.

### 6. Documentos adjuntos

`test_documentos_adjuntos.py`

Estos tests validan que la evidencia documental funcione cuando la contraparte
si adjunta archivos durante el diligenciamiento:

- el flujo cubre los seis documentos requeridos por la interfaz publica:
  `cedula_representante`, `certificado_existencia`, `estados_financieros`,
  `declaracion_renta`, `rut` y `referencias_bancarias`;
- `POST /api/formularios/{formulario_id}/documentos` guarda el archivo en
  storage local bajo `tmp/{codigo_peticion}`;
- el documento queda registrado en `documentos_adjuntos` con tipo, nombre
  sanitizado, `content_type`, tamano, hash SHA-256, `subido_por=CONTRAPARTE` y
  version;
- cada carga dispara una solicitud al `ExtractorIAEnMemoria`, incluyendo una por
  cada uno de los seis tipos documentales;
- `GET /api/formularios/{formulario_id}/documentos` devuelve solo documentos
  activos;
- cargar un nuevo archivo del mismo tipo reemplaza el anterior, conserva la
  trazabilidad con `version_anterior_id`, sube `version_numero` y marca el
  documento previo con borrado logico;
- el documento reemplazado no aparece como activo en el listado;
- el endpoint rechaza tipos documentales fuera del catalogo, extensiones no
  permitidas, `content_type` no permitido y archivos que exceden el tamano
  maximo configurado;
- al radicar, el documento activo se mueve de `tmp/` a la carpeta definitiva de
  la contraparte y la ruta en BD queda actualizada;
- el PDF oficial generado por la radicacion queda en la misma carpeta definitiva;
- si faltan los seis documentos, el backend retorna los seis faltantes exactos;
- si falta uno de los seis documentos, la radicacion se rechaza sin consumir
  acceso, sin generar PDF, sin registrar auditoria y sin emitir alerta;
- despues de cargar el documento faltante, el mismo acceso puede radicar
  normalmente.

### 7. Radicacion con documentos obligatorios

`test_radicacion_formulario.py`

Estos tests cubren el cierre del diligenciamiento con la regla vigente de
negocio: cliente o proveedor solo puede radicar cuando el formulario esta
completo y existen los seis documentos requeridos activos.

Se validan dos variantes porque el formulario tiene reglas distintas por tipo
de persona:

- persona juridica: exige clasificacion tributaria, junta directiva,
  accionistas y beneficiario final;
- persona natural: exige direccion y ciudad de residencia, y no debe persistir
  bloques juridicos aunque lleguen en el payload.

En ambos casos se valida que:

- el portal interno crea el acceso manual con correo obligatorio;
- la contraparte autoguarda un payload minimo completo;
- la contraparte carga los seis documentos obligatorios;
- `POST /api/formularios/{formulario_id}/enviar` responde `valido=true`;
- el formulario cambia de `borrador` a `enviado`;
- se genera el PDF oficial como `FORMULARIO_PDF`;
- el PDF queda registrado en `documentos_adjuntos` con version, hash, tamano,
  snapshot y `subido_por=SISTEMA`;
- el archivo existe en el storage local del harness;
- se registra auditoria `FORMULARIO_ENVIADO` con actor tipo `CONTRAPARTE`;
- se emite alerta interna `FORMULARIO_RECIBIDO`;
- el acceso manual queda consumido mediante `consumed_at`.

Adicionalmente, para persona juridica y persona natural se comprueba el bloqueo
posterior del acceso:

- volver a entrar por token retorna `410`;
- intentar retomar con codigo de peticion + PIN retorna `409`;
- el listado del portal muestra `estado_acceso=consumido`.

### 8. Portal interno de expedientes

`test_expedientes_portal.py`

Este test valida la primera lectura interna despues de una radicacion exitosa:

- un formulario que sigue en `borrador` no aparece en el listado de expedientes;
- un formulario radicado con los seis documentos obligatorios aparece en
  `GET /api/expedientes/`;
- el resumen expone codigo de peticion, razon social, NIT, tipo de contraparte,
  tipo de persona, tipo de solicitud, estado y cantidad de documentos;
- los filtros por `tipo_contraparte` y la busqueda por razon social/codigo de
  peticion retornan el expediente correcto;
- `GET /api/expedientes/{formulario_id}` retorna el detalle con metadatos,
  documentos activos, ausencia de alertas y disponibilidad de firmado en falso;
- el detalle incluye los seis documentos cargados por la contraparte y el PDF
  oficial generado por el sistema;
- `GET /api/expedientes/{formulario_id}/documentos/{doc_id}/descargar`
  descarga el PDF oficial desde el storage local del harness.

### 9. Aprobacion interna de expedientes

`test_expediente_aprobacion.py`

Este test valida la primera decision interna sobre un expediente radicado:

- el analista aprueba con `POST /api/expedientes/{formulario_id}/aprobar`;
- el endpoint responde con estado `validado`;
- el formulario cambia de `enviado` a `validado`;
- se registra auditoria `FORMULARIO_APROBADO` con actor tipo `OPERADOR` y el
  correo del analista autenticado;
- aprobar no emite una nueva alerta al portal interno;
- aprobar no envia notificaciones externas a la contraparte;
- el detalle del expediente refleja el estado `validado`.

### 10. Devolucion para correccion

`test_expediente_devolucion.py`

Este test valida el ciclo de devolucion desde un expediente radicado:

- el analista devuelve con `POST /api/expedientes/{formulario_id}/devolver`;
- el endpoint responde `en_correccion`, correo notificado y correo enviado;
- el formulario cambia de `enviado` a `en_correccion`;
- se incrementa `numero_correccion` y se persisten especificaciones/campos en
  `campos_a_corregir`;
- se registra auditoria `FORMULARIO_DEVUELTO` con actor tipo `OPERADOR` y
  metadata de correccion;
- se reactiva el acceso externo: `consumed_at` vuelve a `NULL` y se genera un
  token nuevo;
- el token anterior deja de resolver y el token nuevo abre el formulario en
  correccion;
- la recuperacion por codigo + PIN vuelve a quedar disponible;
- se emite alerta interna `FORMULARIO_DEVUELTO` con etiquetas legibles de los
  campos a corregir;
- se envia notificacion de devolucion al destinatario con enlace nuevo;
- el detalle del expediente expone `modo_trabajo=correccion`.

Este test tambien protegio una regresion real: la alerta de devolucion debe
llamar el puerto `alertar` con argumentos nombrados, igual que el resto de
alertas del sistema.

### 11. Reenvio de correccion

`test_expediente_reenvio_correccion.py`

Este test valida que la contraparte pueda subsanar y reenviar despues de una
devolucion:

- el destinatario entra con el token nuevo de correccion;
- autoguarda un dato corregido mientras el formulario esta en `en_correccion`;
- reenvia con el token vigente;
- el formulario vuelve a `enviado`;
- el acceso vuelve a quedar consumido;
- se registra un segundo evento `FORMULARIO_ENVIADO` con estado anterior
  `en_correccion`;
- se genera una nueva version del PDF oficial (`version_numero=2`) enlazada a la
  version anterior;
- el snapshot del PDF v2 contiene el dato corregido;
- se emite alerta interna `FORMULARIO_CORREGIDO`;
- el token de correccion queda bloqueado despues del reenvio;
- el detalle del expediente vuelve a `modo_trabajo=""` y conserva el historial de
  versiones del PDF.

### 12. Rechazo definitivo de expediente

`test_expediente_rechazo.py`

Este test valida la decision interna de rechazo definitivo:

- el analista rechaza con `POST /api/expedientes/{formulario_id}/rechazar`;
- el endpoint responde con estado `rechazado`, motivo interno y bandera de
  notificacion enviada;
- el formulario cambia de `enviado` a `rechazado`;
- el acceso externo permanece consumido y no se reactiva;
- se registra auditoria `FORMULARIO_RECHAZADO` con actor tipo `OPERADOR` y el
  motivo interno en metadata;
- se emite alerta interna `FORMULARIO_RECHAZADO` con el motivo interno;
- se envia notificacion de rechazo al destinatario usando solo el mensaje
  redactado para la contraparte;
- el token ya consumido sigue bloqueado;
- el detalle del expediente refleja `estado=rechazado` y no expone modo de
  correccion.

### 13. Envio a firma electronica

`test_expediente_firma.py`

Este test valida el inicio del ciclo de firma despues de aprobar el expediente:

- el analista aprueba el expediente y luego invoca
  `POST /api/expedientes/{formulario_id}/enviar-a-firma`;
- el endpoint responde con `request_id`, estado `pendiente_firma` y correo del
  firmante;
- el formulario cambia de `validado` a `pendiente_firma`;
- se guarda `zoho_request_id` en el formulario;
- se registra auditoria `FIRMA_INICIADA` con actor tipo `OPERADOR`;
- se genera y registra el documento `CERTIFICADO_SAGRILAFT`;
- el doble `ZohoSignEnMemoria` recibe exactamente dos PDFs: formulario oficial
  y certificado;
- la solicitud Zoho usa el correo destinatario y el nombre del representante
  legal como firmante;
- se emite alerta interna `FORMULARIO_ENVIADO_A_FIRMA`;
- el detalle del expediente refleja `pendiente_firma` y todavia no expone
  documento firmado disponible.

### 14. Webhook Zoho

`test_expediente_webhook_zoho.py`

Estos tests validan el procesamiento seguro de webhooks de ZohoSign.

Para el caso valido:

- el expediente se radica, aprueba y envia a firma con `ZohoSignEnMemoria`;
- el webhook se invoca por HTTP real en `POST /api/webhooks/zoho-sign`;
- el cuerpo del webhook se firma con HMAC SHA-256 usando
  `ZOHO_WEBHOOK_SECRET`;
- el endpoint acepta la firma valida y responde `{"ok": true}`;
- el formulario cambia de `pendiente_firma` a `firmado`;
- se conserva `zoho_request_id` y se guarda `ruta_documento_firmado`;
- el documento firmado descargado desde Zoho fake se guarda en storage;
- se registra auditoria `FIRMA_COMPLETADA` con actor tipo `SISTEMA`;
- se emite alerta interna `FORMULARIO_FIRMADO`;
- el detalle del expediente expone `documento_firmado_disponible=true`;
- `GET /api/expedientes/{formulario_id}/documento-firmado` descarga el PDF
  firmado conservado.

Para el caso invalido:

- el webhook usa el mismo body de finalizacion, pero con firma HMAC incorrecta;
- el endpoint responde `403` y mensaje de token de webhook invalido;
- el formulario permanece en `pendiente_firma`;
- no se registra auditoria `FIRMA_COMPLETADA`;
- no se guarda `ruta_documento_firmado`;
- no se emite alerta `FORMULARIO_FIRMADO`;
- la descarga del documento firmado sigue respondiendo `404`.

Para el caso duplicado:

- el mismo webhook valido se recibe dos veces con el mismo `request_id`;
- ambas llamadas responden `200`;
- el formulario permanece en `firmado`;
- no se crea un segundo evento `FIRMA_COMPLETADA`;
- no se emite una segunda alerta `FORMULARIO_FIRMADO`;
- no se reemplaza la ruta del documento firmado ya conservado.

### 15. Cierre de expediente

`test_expediente_cierre.py`

Estos tests validan el cierre funcional del expediente.

Para el cierre con informe final:

- el expediente recorre el ciclo radicado, aprobado, enviado a firma y firmado;
- el analista carga el informe final con
  `POST /api/expedientes/{formulario_id}/reporte-final`;
- la causal usada es `informe_final`;
- el endpoint responde `cerrado`, `reporte_final_cargado=true` y
  `version_numero=1`;
- se registra documento `REPORTE_FINAL` en BD y storage;
- el reporte queda bajo `reportes_finales/`;
- se persisten nombre, content type, tamano, hash, actor y version;
- se registra auditoria `REPORTE_FINAL_CARGADO` con causal y justificacion;
- se emite alerta interna `REPORTE_FINAL_CARGADO`;
- el detalle del expediente expone estado `cerrado` y `causal_cierre`;
- el reporte final aparece en los documentos del expediente y puede descargarse.

Para el cierre sin informe final:

- el expediente tambien recorre el ciclo hasta `firmado`;
- el analista cierra por causal `no_continuacion_dialogos` sin adjuntar archivo;
- el endpoint responde `cerrado`, `reporte_final_cargado=false` y sin version;
- no se registra documento `REPORTE_FINAL`;
- se registra auditoria `EXPEDIENTE_CERRADO`;
- la metadata conserva causal, justificacion y `requiere_reporte_final=false`;
- no se emite alerta de reporte final cargado;
- el detalle del expediente expone la causal de cierre y no lista reporte final.

Este test tambien protegio una regresion real: el detalle del expediente cerrado
debe leer `causal_cierre` tanto desde `EXPEDIENTE_CERRADO` como desde
`REPORTE_FINAL_CARGADO`, porque el cierre con informe final usa este ultimo
evento.

### 16. Comparacion de versiones

`test_comparacion_versiones.py`

Este test valida la evidencia de cambios despues de una correccion:

- el expediente se radica con PDF oficial version 1;
- el analista devuelve el expediente solicitando corregir `telefono`;
- la contraparte corrige el telefono y reenvia;
- el reenvio genera PDF oficial version 2 enlazado a la version 1;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones` compara la
  ultima version contra la anterior;
- la respuesta queda disponible y reporta exactamente un cambio: `telefono`;
- el valor anterior es `6015550101` y el corregido es `6015559999`;
- no se reportan cambios inventados en campos no modificados;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones-especificas`
  devuelve la misma diferencia al pasar explicitamente los IDs de PDF v1 y v2;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones/reporte-pdf`
  genera un PDF descargable de evidencia.

### 17. Rate limiting en endpoints sensibles

`test_rate_limiting.py`

Estos tests validan límites de abuso sobre endpoints públicos sensibles:

- `POST /api/formularios/sesion/recuperar-por-acceso` permite hasta 5 intentos
  por minuto por cliente;
- cinco intentos con PIN incorrecto responden `401`;
- el sexto intento responde `429` con mensaje controlado;
- `POST /api/formularios/{formulario_id}/enviar` permite hasta 10 intentos por
  minuto por cliente;
- diez envíos con token incorrecto responden `401`;
- el intento once responde `429`;
- el harness limpia los contadores del rate limiter entre pruebas para evitar
  falsos positivos.

### 18. RBAC del portal interno por tipo de contraparte

`test_rbac_expedientes.py`

Estos tests validan que los roles entregados por Keycloak controlen que carpetas
puede ver y operar cada usuario interno:

- `acceso_clientes` permite listar y operar solo accesos manuales y expedientes
  de tipo `cliente`;
- `acceso_proveedores` permite listar y operar solo accesos manuales y
  expedientes de tipo `proveedor`;
- un usuario con ambos roles ve y opera clientes y proveedores;
- un usuario sin ninguno de estos roles recibe `403 Acceso denegado`;
- intentar crear un acceso manual de una contraparte no autorizada se rechaza;
- intentar reenviar credenciales de un acceso manual no autorizado se rechaza y
  no modifica el registro;
- intentar consultar o aprobar un expediente no autorizado se rechaza;
- un intento de aprobacion no autorizado no cambia el estado del expediente ni
  registra auditoria de aprobacion.

### 19. Migraciones Alembic sobre PostgreSQL

`test_migraciones_alembic_postgres.py`

La validación objetivo usa **PostgreSQL 16 local y desechable**. El ejecutor
[`scripts/test_migrations_pg16.py`](../../scripts/test_migrations_pg16.py) exige
binarios 16.x, crea un clúster nuevo en `/tmp`, escucha solo en un socket Unix
privado (sin TCP) y elimina el clúster al terminar. Cada caso de integración crea
y elimina además su propia base `sagrilaft_alembic_test_*`. No utiliza AWS, Docker,
RDS, staging ni datos de una base existente.

```bash
venv/bin/python scripts/test_migrations_pg16.py \
  --pg-bin /ruta/postgresql-16/bin \
  --report-dir /tmp/validacion-pg16-nueva
```

El directorio de evidencias debe ser nuevo. Conserva versión del servidor,
`pytest.txt`, `pytest.xml`, `postgres.log`, `database-check.json` (incluye bases
residuales) y `cleanup.txt`. Necesita `initdb`, `pg_ctl`, `postgres` y las dependencias
Python de pruebas. Si el entorno restringe sockets Unix, hay que permitir la ejecución
local del servidor; no sustituirlo por una URL de RDS o una base existente.

El ejecutor fija `TEST_POSTGRES_EXPECTED_MAJOR=16`; las pruebas verifican la versión
antes de crear bases. La invocación directa de pytest sin `TEST_POSTGRES_ADMIN_URL`
omite los casos que necesitan PostgreSQL: **una ejecución con skips no acredita PG16**.
El ejecutor también incluye `tests/unit/test_migration_guard.py`.

Cobertura:

- Las **28 revisiones**, recorridas individualmente en orden del grafo, merge de
  ramas, head `f8a9b0c1d2e3` y repetición de `upgrade head`.
- Actualización desde ambas ramas con una fila sintética conservada.
- Datos de persona natural/jurídica: residencia, clasificación tributaria, fechas
  ISO y meses españoles, bisiestos, vacíos, valores inválidos, redondeo monetario y
  conversión de textos booleanos. Fechas inválidas pasan a NULL y textos booleanos
  no reconocidos a false: se acredita ese comportamiento, no su validez de negocio.
- Rechazo y rollback transaccional de CHECK inválidos, desbordamiento NUMERIC y
  correo destinatario NULL; corrección/reintento para CHECK y correo.
- Snapshot ausente, columna antigua y coexistencia de columnas; conservación del
  JSON, versión del documento, trigger de auditoría, supresión de evento desde la
  aplicación, índice y cascada de borrado.
- Once pruebas funcionales/estructurales adicionales sobre el head: todas las tablas
  y columnas del ORM actual existen; crear/guardar/leer/actualizar firma y ambos
  contactos mediante repositorios actuales; las siete listas se crean juntas y se
  actualizan/vacían individualmente sin modificar las demás. Las lecturas usan
  sesiones nuevas para comprobar persistencia tras commit, sin `create_all`.
- Lock PostgreSQL entre conexiones, espera acotada, liberación tras errores y
  commit, bloqueo efectivo de Alembic, revisión previa/final, rechazo de head
  incorrecto y separación entre arranque normal y modo migración.

**Resultado local del 2026-10-06:** PostgreSQL **16.6**, compilado desde el tarball
oficial bajo `/tmp`, GCC 15 con `-std=gnu17`, locale `C`, sin ICU. **44 passed,
3 xfailed**, más cinco advertencias de deprecación Pydantic. No se modificaron las
28 migraciones ni el código de despliegue. PostgreSQL 17 no se usó como sustituto.

Los tres `xfail(strict=True, raises=AssertionError)` son **defectos de conservación
reproducidos**, no aprobaciones de seguridad de datos:

| Revisión | Dato sintético perdido al actualizar |
|---|---|
| `c3f1a2b4d5e6` | `fecha_firma` no se copia a día/mes/año |
| `c8d9e0f1a2b3` | Contacto de órdenes no se copia a `contactos` |
| `b7e4f2a19c3d` | Lista de accionistas no se copia a su tabla normalizada |

Un error distinto de la aserción de conservación no queda oculto como fallo esperado.
Si una corrección hace pasar alguno de estos casos, el XPASS estricto obliga a revisar
la marca. No se reescriben aquí migraciones históricas potencialmente aplicadas.

**Criterio aceptado para staging:** no se requiere conservar sus datos de prueba.
Los tres fallos históricos de conservación no bloquean ese objetivo estructural.
Las 11 pruebas funcionales/estructurales pasan en PG16.6: no se encontraron tablas
ni columnas faltantes para el ORM ni incompatibilidades en los repositorios probados.
Esto no acredita el servicio externo de firma, la API completa ni el estado vivo de
staging. Las consultas posteriores de revisión/código están registradas por separado
en [Estado](../../docs/estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).

**Antes de ejecutar en staging:** revalidar la revisión y el salto registrados en Estado. La pérdida de
los datos de prueba descritos está aceptada; no se exige backfill para ellos. Auditar
NULL, formatos/rangos y datos fuera de límites que puedan impedir la migración. Esta muestra no certifica todos los registros posibles ni
compatibilidad del código anterior con el esquema final. Falta ensayar el salto real
con datos anonimizados representativos, roles/permisos y configuración RDS, su versión
menor concreta y collation, duración/bloqueos con volumen y recuperación. La versión
16.6 ensayada no se propone como selección de parche para producción.

La evidencia previa de `2 passed` sobre el contenedor local `solucion-postgres-1`
correspondía al alcance anterior; no acreditaba estas pruebas ni PostgreSQL 16.

## Resultados históricos de la suite

La cobertura por endpoint y sus invariantes se describe en
[Tipos de test](#tipos-de-test-de-integracion-implementados-hoy).
Los conteos siguientes pertenecen a la ejecución registrada, no a una nueva
corrida sobre el HEAD actual. La comparación PostgreSQL del 1 de octubre se
conserva en la [evidencia local](../../docs/evidencia/e2e-staging/VALIDACION_STAGING_E2E.md).

Resultado de verificacion:

```text
venv/bin/pytest tests/integration -q
Sin TEST_POSTGRES_ADMIN_URL: 42 passed, 1 skipped
Con TEST_POSTGRES_ADMIN_URL: 43 passed

venv/bin/pytest -q
Sin TEST_POSTGRES_ADMIN_URL: 77 passed, 1 skipped
Con TEST_POSTGRES_ADMIN_URL: 78 passed
```

## De Que Forma

La validacion se hizo con pruebas HTTP reales contra la aplicacion FastAPI:

- `cliente_api` levanta Uvicorn en `127.0.0.1` y llama endpoints reales con
  `httpx.Client`;
- cada test usa una base SQLite aislada creada desde los modelos SQLAlchemy
  reales;
- `get_db` se sobreescribe para entregar la sesion de prueba;
- `portal_interno` se sobreescribe con un usuario interno de prueba;
- `obtener_servicio_email` se sobreescribe con `NotificadorEnMemoria`;
- AWS, Zoho, Keycloak, SES/SNS y Bedrock no se ejecutan realmente;
- los dobles en memoria guardan efectos secundarios para poder afirmarlos.

Los tests agregados ejercitan endpoints reales:

- `POST /api/accesos-manuales/`;
- `GET /api/accesos-manuales/`;
- `POST /api/accesos-manuales/{acceso_id}/reenviar`;
- `GET /api/accesos-manuales/token/{token}`;
- `PUT /api/formularios/{formulario_id}`;
- `POST /api/formularios/{formulario_id}/documentos`;
- `GET /api/formularios/{formulario_id}/documentos`;
- `POST /api/formularios/sesion/recuperar-por-acceso`;
- `POST /api/formularios/{formulario_id}/enviar` para validar el rechazo de
  credenciales invalidas, formularios incompletos, documentos faltantes y la
  radicacion valida con los seis documentos obligatorios, ademas de rate limiting
  por token incorrecto;
- `GET /api/expedientes/`;
- `GET /api/expedientes/{formulario_id}`;
- `GET /api/expedientes/{formulario_id}/documentos/{doc_id}/descargar`;
- `POST /api/expedientes/{formulario_id}/aprobar`;
- `POST /api/expedientes/{formulario_id}/devolver`;
- `POST /api/expedientes/{formulario_id}/rechazar`;
- `POST /api/expedientes/{formulario_id}/enviar-a-firma`;
- `POST /api/expedientes/{formulario_id}/reporte-final`;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones`;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones-especificas`;
- `GET /api/expedientes/{formulario_id}/comparacion-versiones/reporte-pdf`;
- `POST /api/webhooks/zoho-sign`;
- `GET /api/expedientes/{formulario_id}/documento-firmado`.

La prueba de migraciones ademas ejecuta Alembic de forma programatica con:

- `alembic upgrade head`;
- conexion administrativa definida por `TEST_POSTGRES_ADMIN_URL`;
- base temporal creada y destruida por test.

En otras palabras: no se testeo solo un schema ni una funcion aislada. Se valido
la colaboracion entre router, schema, dependencias, servicio, repositorio,
modelo de BD y dobles de integraciones externas.

## Alcance de esta suite y validaciones externas ya realizadas

La validación funcional PostgreSQL de 12 escenarios y las migraciones desde
cero ya fueron ejecutadas; no quedan como pendientes generales de staging.

Esta suite usa dobles y por sí sola no valida integraciones reales contra:

- AWS Bedrock;
- S3;
- SES;
- SNS;
- Keycloak real;
- Zoho Sign real;
- API real de listas de cautela.

La validación externa de Bedrock, S3, correo, Keycloak y Zoho ya está
registrada en el [E2E de AWS staging](../../docs/evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md).
SNS→correo se validó en el [runbook](../../docs/operacion/RUNBOOK_OPERATIVO.md).
La API real de listas continúa diferida hasta contratar proveedor; producción
arranca con listas deshabilitadas. Las validaciones productivas siguen abiertas.

## Por Que Un Harness

Un harness es una base comun de ejecucion para pruebas. En este proyecto es
necesario por razones concretas:

1. El sistema tiene muchos bordes externos.

   Sin harness, cada test tendria que decidir como evitar AWS, Zoho, correo y
   Keycloak. Eso generaria duplicacion e inconsistencias.

2. Los flujos importantes son transaccionales.

   Crear acceso, radicar, devolver, firmar y cerrar no son funciones aisladas:
   atraviesan API, servicios, repositorios, storage, auditoria y alertas. El
   harness permite probar esa colaboracion completa.

3. Se necesita determinismo.

   Los tests no pueden depender de red, credenciales, disponibilidad de terceros
   ni tiempos de respuesta externos. Los dobles en memoria hacen que cada prueba
   tenga entradas y salidas controladas.

4. Se necesita observar efectos secundarios.

   En SAGRILAFT no basta con que un endpoint retorne 200. Tambien hay que saber
   si se creo una alerta, si se intento enviar un correo, si se genero una
   solicitud Zoho o si se guardo un archivo. Los dobles guardan esos eventos para
   afirmarlos explicitamente.

5. Protege contra regresiones de arquitectura.

   Si alguien rompe la inyeccion de dependencias, el storage, la configuracion o
   los repositorios, las pruebas de integracion fallan antes de llegar a staging.

6. Mantiene lenguaje ubicuo.

   Los nombres del harness hablan el idioma del dominio:
   `NotificadorEnMemoria`, `AlertasPortalEnMemoria`, `ExtractorIAEnMemoria`,
   `ZohoSignEnMemoria`, `usuario_portal`, `cliente_api`, `sesion_bd`.

## Por Que Se Hizo De Esta Manera

Se eligio HTTP real con Uvicorn porque el cliente in-process de FastAPI/httpx se
quedaba bloqueado en este entorno incluso con una aplicacion minima. Levantar la
app en loopback mantiene una prueba muy cercana al runtime real y evita esa
incompatibilidad.

Se desactivo el lifespan productivo porque su responsabilidad es inicializar
adaptadores reales. En pruebas de integracion local queremos la aplicacion real,
pero con adaptadores controlados. Por eso el fixture instala `app.state.config`,
`app.state.storage`, `app.state.orchestrator`, `app.state.zoho_sign` y
`app.state.alertas_portal` directamente.

Se uso SQLite en memoria para arrancar rapido y permitir una primera fase de
integracion sin Docker ni Postgres. Para que el harness pueda ejecutar el flujo
de radicacion, la capa de persistencia evita ejecutar `SET LOCAL` cuando el
dialecto no es PostgreSQL y el identificador autoincremental de auditoria usa
`Integer` solo bajo SQLite. En PostgreSQL se mantiene el comportamiento real:
marca transaccional para triggers y columna `BIGINT`.

La segunda variante con PostgreSQL ya está implementada y fue ejercitada en
los 12 escenarios registrados. Conservar ambas variantes y ampliar la cobertura
no equivale a repetir como pendiente la creación del harness.

## Seguimiento de mejoras

El trabajo de cobertura adicional y PostgreSQL en CI se mantiene en
[P19](../../docs/produccion/PENDIENTES_PRODUCCION.md#p19). Este archivo describe
el harness, los comandos y sus límites; no mantiene otra lista de tareas.
