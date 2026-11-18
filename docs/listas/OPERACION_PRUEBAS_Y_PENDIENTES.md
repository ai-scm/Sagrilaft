# Módulo de listas cautelares: operación, pruebas y pendientes

Estado verificado contra el código el 2026-11-13. Todo lo que se describe aquí funciona
**solo en local** (`development`/`test`). Ningún ambiente compartido tiene el módulo
v2 operativo, y producción está bloqueada por código.

Documentos relacionados: [arquitectura](ARQUITECTURA_LISTAS.md) (componentes,
contratos, rutas, decisiones) y [reglas de búsqueda](BUSCADOR_REGLAS_Y_CASOS.md)
(clasificación y casos).

---

## 1. Puesta en marcha local

El `docker-compose.dev.yml` levanta el backend y un servicio **`trabajador-listas`**
(`python -m infrastructure.listas.trabajador_local`). El trabajador comparte imagen,
base y custodia (`backend/uploads/listas`, montada en `/app/uploads/listas`). No expone
rutas: solo procesa trabajos ya admitidos y nunca aprueba ni activa versiones.

El trabajador necesita `SECRET_KEY` igual que el backend: su primer arranque falló por no
tenerla, y el Compose ahora la exige. El trabajador se niega a arrancar si `APP_ENV` no es `development`, si la base no está en
el host `postgres` del Compose o si `LISTAS_BASE_LOCAL` no coincide con el nombre de la
base. Ejecuta siempre las consultas y, con `LISTAS_ADMIN_HABILITADA=true`, también la
validación, la importación, la comparación y la preparación de búsqueda.

Variables del Compose (todas con valor seguro por defecto):

| Variable | Defecto | Para qué |
|---|---|---|
| `LISTAS_IMPLEMENTACION` | `deshabilitado` | Modalidad de consulta: `simulado`, `archivos`, `externo` o `deshabilitado` |
| `PROVEEDOR_LISTAS_CAUTELA` | `""` | Variable heredada; vacía se ignora |
| `LISTAS_SIMULACION_ESCENARIO` | — | Obligatoria con `simulado`: `sin_coincidencias_v1`, `coincidencia_v1`, `parcial_v1` o `error_v1` |
| `LISTAS_ADMIN_HABILITADA` | `false` | Habilita recepción y administración |
| `LISTAS_OFAC_LOCAL_HABILITADA` | `false` | Añade `ofac_sdn` a las fuentes administrables |
| `LISTAS_ARCHIVOS_FUENTES_HABILITADAS` | — | Alternativa genérica: lista de fuentes administrables (no está en el Compose) |
| `LISTAS_ARCHIVOS_LOCAL_HABILITADA` | `false` | Habilita consultas por archivos |
| `LISTAS_ARCHIVOS_FUENTES` | — | Fuentes requeridas en cada consulta, por ejemplo `ofac_sdn` |
| `LISTAS_ARCHIVOS_POLITICA_ID` | — | UUID de una política con `solo_pruebas: true` |
| `LISTAS_ADMIN_POLITICA_ID` | — | UUID de la política administrativa (`solo_pruebas` o `uso_local`) |
| `LISTAS_CUSTODIA_DIRECTORIO` | `/app/uploads/listas` | Custodia de originales e informes |
| `LISTAS_BASE_LOCAL` | `${POSTGRES_DB}` | Protección del trabajador local |

Roles necesarios en el Keycloak local (ver
[permisos](ARQUITECTURA_LISTAS.md#8-seguridad-y-permisos)): `listas_cargador` y
`listas_aprobador` para administrar (pueden estar en la misma cuenta), y
`listas_operador` o `listas_revisor` más `acceso_clientes`/`acceso_proveedores`
para consultar. Su existencia en Keycloak no se ha verificado: hay que crearlos y
asignarlos desde la consola.

## 2. Perfiles y límites

El adaptador de cada fuente fija su perfil (`domain/listas/administracion.py`). Son
límites de ensayo, **no capacidades certificadas**.

| Límite | Sintético `f5-sintetico-v1` | OFAC `ofac-advanced-local-v2` |
|---|---|---|
| Archivo recibido | 100 MiB | 256 MiB (también en SQL, migración `f76a89b012c3`) |
| Expandido / entradas ZIP / relación | 500 MiB / 20 / 100:1 | igual |
| Profundidad XML, texto, atributo | 64 / 1 MiB / 8 KiB | igual |
| Elementos XML | 2 millones | 10 millones |
| Memoria de validación | 1 GiB | 2 GiB |
| Disco temporal | 2 GiB | 4 GiB |
| Lote de importación | 1.000 registros | 100 registros |
| Comparación | 10.000 registros / 16 MiB | 50.000 registros / 128 MiB |
| Carga y validación / intento | 300 s / 1.800 s | igual |
| Concesión / latido / recuperaciones | 120 s / 30 s / 3 | igual |
| Concurrencia | 1 carga por actor, 2 globales, 1 trabajador administrativo | igual |

Otros límites:

- Metadatos de recepción: 16 KiB, recibidos en un máximo de 30 s.
- Cuerpos administrativos: 16 KiB.
- Concesión de la transferencia: 330 s.
- Tres transferencias por recepción.
- El lector OFAC usa un índice SQLite temporal anónimo de hasta 512 MiB, que se libera
  al morir el proceso.

Sobrepasar un límite rechaza la operación. Nunca se trunca para hacerla caber.

## 3. Cargar y activar una lista OFAC

### 3.1 Requisito previo sin herramienta

Una fuente y una política deben existir en la base antes de cargar:

- **Fuente `ofac_sdn` en `fuente_lista`.** La crea
  `RepositorioAdministracionListas.crear_fuente`; la recepción nunca crea fuentes.
- **Política en `politica_listas`.** Lleva `parametros` (`solo_pruebas: true` o
  `uso_local: true`), una `huella` igual a `services.listas.informes.calcular_huella(parametros)`
  y la identidad del aprobador (`aprobador_emisor`, `aprobador_sujeto`). Su UUID va en
  `LISTAS_ADMIN_POLITICA_ID` y, para consultar, en `LISTAS_ARCHIVOS_POLITICA_ID` (este
  exige `solo_pruebas: true`).

**Hoy no hay ruta, script ni migración que registre la fuente o la política.** Solo lo
hacen los fixtures de `tests/persistencia_listas/` y lo hacía el script de la demo F6,
que se eliminó. Esto está en [pendientes](#7-pendientes).

### 3.2 Pasos

1. **Descargar a mano** el SDN Advanced (XML o ZIP) desde
   `https://sanctionslist.ofac.treas.gov/Home/SdnList` y anotar la fecha y hora reales de
   descarga. No hay descarga automática, y la fecha de publicación (`DateOfIssue` del XML)
   no sustituye a la de descarga.
2. **Revisión opcional sin base de datos**: valida el XSD y la proyección, y mide
   conteos y tiempo.

   ```sh
   venv/bin/python scripts/validacion/revisar_ofac_local.py RUTA/sdn_advanced.zip \
     --formato OFAC_ADVANCED_ZIP_V3 --resultado /tmp/ofac-revision.json
   ```

3. **Cargar** con un JWT de `listas_cargador`. La CLI solo habla con `http://127.0.0.1`,
   pide el token sin mostrarlo o lo lee de un archivo, y exige `--descargado-en` para
   formatos OFAC:

   ```sh
   venv/bin/python scripts/listas/cargar_sintetico.py RUTA/sdn_advanced.zip \
     --formato OFAC_ADVANCED_ZIP_V3 --clave ofac-AAAAMMDD \
     --descargado-en 2026-11-06T10:30:00-05:00 --token-archivo RUTA/jwt.txt
   ```

   Con la misma clave, la CLI recupera la recepción en lugar de duplicarla. Si cambian
   los bytes, hace falta otra clave.
4. **Validación e importación.** Las hace solas el `trabajador-listas`. El progreso se
   consulta en `GET /api/administracion-listas/intentos/{id}` y el informe en
   `/recepciones/{id}/validacion`. La versión queda `VALIDA` e **inactiva**.
5. **Comparar, solicitar, decidir y ejecutar** con
   `scripts/listas/administrar_sintetico.py`. Sirve para cualquier fuente habilitada,
   pese a su nombre. Operaciones: `comparar`, `informe`, `solicitar`, `consultar`,
   `decidir`, `ejecutar`, `revocar` y `bloquear`.

   ```sh
   venv/bin/python scripts/listas/administrar_sintetico.py comparar --datos comparacion.json --token-archivo jwt.txt
   venv/bin/python scripts/listas/administrar_sintetico.py informe --id UUID_COMPARACION --token-archivo jwt.txt
   venv/bin/python scripts/listas/administrar_sintetico.py solicitar --datos solicitud.json --token-archivo jwt.txt
   venv/bin/python scripts/listas/administrar_sintetico.py decidir --id UUID_SOLICITUD --datos decision.json --token-archivo jwt.txt
   venv/bin/python scripts/listas/administrar_sintetico.py ejecutar --id UUID_SOLICITUD --datos ejecucion.json --token-archivo jwt.txt
   ```

   Cuerpos, con los UUID obtenidos en cada paso y una clave distinta por operación:

   ```json
   {"fuente_id":"UUID_FUENTE","destino_id":"UUID_VERSION","revision_esperada":0,"clave":"comparar-v1"}
   {"comparacion_id":"UUID_COMPARACION","politica_id":"UUID_POLITICA","tipo":"ACTIVACION","motivo":"Revisión de la publicación del 2026-11-06","clave":"solicitar-v1"}
   {"solicitud_id":"UUID_SOLICITUD","decision":"APROBADA","motivo":"Informe y original revisados","clave":"aprobar-v1"}
   {"solicitud_id":"UUID_SOLICITUD","aprobacion_id":"UUID_REVISION","revision_esperada":0,"clave":"ejecutar-v1"}
   ```

   El informe de comparación necesita que el trabajador haya procesado antes la
   comparación. Para restaurar se usa `tipo: "REVERSION"`, con una comparación nueva y la
   revisión actual del puntero.
6. **Preparación de búsqueda.** Tras la activación, el trabajador prepara sola la
   generación de búsqueda.
7. **Consultar.** Se configuran `LISTAS_IMPLEMENTACION=archivos`,
   `LISTAS_ARCHIVOS_LOCAL_HABILITADA=true`, `LISTAS_ARCHIVOS_FUENTES=ofac_sdn` y
   `LISTAS_ARCHIVOS_POLITICA_ID`, y se reinicia el backend. Se consulta desde
   **Verificar SAGRILAFT** en el portal.

### 3.3 Errores y qué hacer

| Situación | Qué hacer |
|---|---|
| 401 | Obtener un JWT vigente; no desactivar la autenticación |
| 403 | Revisar los roles de la cuenta |
| 404 al abrir una recepción ajena | Es intencional: el original de una recepción solo lo ve su cargador. Se usa `/versiones/{id}/evidencias/original` |
| 409 por una clave reutilizada con otro contenido | Usar una clave nueva para una operación distinta |
| 409 por revisión antigua o «la selección activa cambió» | Comparar y solicitar de nuevo; no ajustar números a mano |
| 409 «La política administrativa cambió» | La solicitud fija la política; crear otra solicitud |
| Respuesta perdida tras ejecutar | Repetir exactamente la misma petición y clave |
| Archivo inválido | Leer su informe; no puede convertirse en versión |
| Proceso interrumpido | Dejar que el trabajador lo retome al vencer la concesión; no reabrir intentos por SQL |
| Versión bloqueada o evidencia corrupta | No activar otra automáticamente; requiere una operación revisada |

No existen todavía ni la reanudación manual de una recepción ni la reconstrucción forzada
de una versión sellada. Un intento terminal se recupera con una recepción nueva del mismo
contenido.

Cómo se recupera cada paso tras una caída:

- **Carga interrumpida.** No continúa desde el último byte: se reenvía el archivo completo
  a la misma recepción cuando vence la concesión (330 s), con un máximo de tres
  transferencias. Hasta entonces un reintento responde 409. El temporal parcial queda sin
  referencia, cuenta para la cuota y aparece en `/conciliacion`; no se borra solo.
- **Validación.** Tiene hasta tres reclamaciones. Agotarlas deja el intento FALLIDO y la
  API muestra `NO_COMPLETADA` con `REINTENTOS_AGOTADOS`; no queda como pendiente. Un
  archivo válido deja el intento `EN_CURSO / IMPORTACION` esperando al importador, con
  cero registros. Una caída puede dejar un directorio temporal `validacion-*`.
- **Importación.** Reanuda desde el último lote confirmado tras vencer la concesión. El
  tiempo consumido se acumula (máximo 1.800 s por versión) y no se reinicia con otro
  trabajador. Una caída después del sellado se reconoce como trabajo terminado.
- **Comparación y ejecución.** Si el proceso muere antes del commit, el trabajo sigue
  pendiente; si muere después, no se repite.

### 3.4 Estado conocido del entorno local

Según el registro del 2026-11-08, no verificado de nuevo:

- La base PostgreSQL del Compose de desarrollo se migró hasta `k21f34a567b8`, después de
  un respaldo en `tmp/respaldo-local-f6/aprobacion-20261108-211655/` (carpeta ignorada
  por Git). No se crearon activaciones ni aprobaciones en ese paso.
- Keycloak local rechazó con HTTP 401 las credenciales de administración configuradas,
  así que los roles `listas_*` no se asignaron a ninguna cuenta. Hay que hacerlo desde la
  consola de Keycloak sin crear cuentas nuevas.
- La copia OFAC del 2026-11-06 no tiene acreditada su fecha real de descarga; en los
  ensayos se registró como copia local. Para una carga real hay que declarar la fecha
  verdadera.
- La custodia local (`backend/uploads/listas/`) contiene esa copia (ver sección 4) y
  archivos de otras pruebas locales.

## 4. Cómo se prueba

| Qué | Comando | Necesita |
|---|---|---|
| Contratos, motor, configuración y archivos (sin base) | `env AWS_EC2_METADATA_DISABLED=true PYTHONPATH=backend venv/bin/python -m pytest -q -p no:cacheprovider tests/contracts tests/validacion_archivos tests/unit/test_trabajador_listas_local.py tests/unit/test_autenticacion_jwt_pyjwt.py` | — |
| Persistencia, HTTP, trabajador, navegador y migraciones | `venv/bin/python scripts/validacion/probar_listas_postgres.py --binarios-postgres /usr/lib/postgresql/17/bin --directorio-resultados /tmp/listas-NUEVO [--seleccion EXPR]` | Binarios de PostgreSQL 17, sockets locales, Chromium de Playwright y `pdftotext`. El directorio de resultados debe ser nuevo |
| Endpoints del portal | `env -i PATH="$PATH" LANG=C.UTF-8 AWS_EC2_METADATA_DISABLED=true venv/bin/python -m pytest -q tests/integration --ignore=tests/integration/test_migraciones_alembic_postgres.py` | Sockets locales |
| Ensayo OFAC completo | `probar_listas_postgres.py … --archivo-ofac RUTA --seleccion importacion_ofac_completa` | El XML o ZIP exactos de la publicación del 2026-11-06 |
| Anclas oficiales R-01–R-04 | `probar_listas_postgres.py … --archivo-ofac RUTA.zip --seleccion f66_ofac_oficial` | El ZIP exacto |

El arnés crea un PostgreSQL propio en `/tmp/listas-f2-*`, sin TCP y sin heredar
credenciales. Migra desde cero, opera con el rol restringido `aplicacion_listas`, levanta
API y Vite en loopback y borra base y custodia al terminar, conservando los resultados.
Nunca usa una base existente.

Regresión completa recomendada antes de entregar un cambio del módulo: el arnés sin
`--seleccion`, más los contratos y los endpoints de la tabla anterior, más
`tests/unit/test_crear_storage.py`, `tests/unit/test_storage_desarrollo_local.py` y
`tests/unit/test_migration_guard.py`. Si se tocó el portal, comprobar también que compila
con `npm --prefix frontend run build:portal`.

Mapa de las pruebas del módulo:

| Área | Archivos |
|---|---|
| Contratos 2.0, configuración y circuito retirado | `tests/contracts/test_listas_v2.py`, `test_listas_cautela_fuente_unica.py`, `test_configuracion_f64.py`; `tests/integration/test_sagrilaft_feature_flag.py` (rutas 410) |
| Administración y catálogos | `tests/contracts/test_administracion_f5.py`, `test_catalogo_fuentes_dominio.py`, `test_catalogo_adaptadores_archivos.py` |
| Validación de archivos y adaptador OFAC | `tests/validacion_archivos/test_archivos_f53.py`, `test_adaptador_ofac.py` |
| Buscador | `tests/contracts/test_busqueda_f61.py`, `test_lectura_busqueda_f62.py`, `test_motor_busqueda_f63.py`, `test_presentacion_f65.py` |
| Persistencia, HTTP, trabajadores y aceptación (solo con el arnés) | `tests/persistencia_listas/`: `test_historial.py`, `test_flujo_http.py`, `test_recepcion_f52.py`, `test_validacion_f53.py`, `test_importacion_f54.py`, `test_administracion_f55.py`, `test_recorrido_f56.py`, `test_ofac_archivos.py`, `test_busqueda_f62.py`, `test_motor_f63_local.py`, `test_integracion_f64.py`, `test_presentacion_f65.py`, `test_aceptacion_f66.py`, `test_integridad_generacion_f66.py`, `test_ofac_busqueda_f66.py`, `test_importacion_ofac_completa.py`, `test_preparacion_automatica.py` |
| Migraciones (con el arnés) | `tests/integration/test_migraciones_alembic_postgres.py` (incluye los tres `xfail`) |
| Autenticación y trabajador local | `tests/unit/test_autenticacion_jwt_pyjwt.py`, `tests/unit/test_trabajador_listas_local.py` |
| Navegador | `tests/navegador_listas/flujo.mjs`, lanzado por `test_flujo_http.py` |

Trabajadores del arnés (`scripts/validacion/ejecutar_trabajador_listas.py`,
`ejecutar_validacion_archivos.py`, `ejecutar_importacion_archivos.py`,
`ejecutar_comparacion_listas.py`). Las pruebas los lanzan como procesos separados.
**Solo aceptan el clúster desechable del arnés** (`LISTAS_PRUEBA_URL` y
`LISTAS_PRUEBA_DIRECTORIO` bajo `/tmp/listas-f2-*`) y usan el rol `aplicacion_listas`.
No sirven para operar el Compose local ni ningún ambiente; para eso está el servicio
`trabajador-listas`. Las CLI de `scripts/listas/` solo hablan con
`http://127.0.0.1` (opción `--url`, por defecto `http://127.0.0.1:8000`).

Selecciones útiles para `--seleccion`: `recepcion`, `sigkill`, `importacion_f54`,
`administracion_f55`, `recorrido_f56`, `f62`, `f63`, `f64`, `f65`,
`'f66 and not ofac_oficial'` (los 26 casos), `test_flujo_http` y `navegador`.

Reglas de las pruebas del módulo:

- Las pruebas HTTP firman JWT con claves locales efímeras y pasan por la validación
  real. **No usar `PORTAL_AUTH_DISABLED`** ni sustituir la autenticación por un usuario
  permitido; eso no prueba permisos.
- No se ajustan los resultados esperados para que una prueba pase ni se convierte un
  fallo nuevo en `xfail`.
- Se cuentan casos distintos, sin sumar repeticiones.
- `LISTAS_F63_EVIDENCIAS_DIRECTORIO`, si se define al ejecutar
  `tests/contracts/test_motor_busqueda_f63.py`, guarda en JSON las clasificaciones y la
  calibración de ejemplo del motor.

Datos de prueba:

- `tests/fixtures/listas_f5/` es la lista sintética de la fuente `ofac_sdn_prueba`: XSD
  propio (espacio de nombres `urn:sagrilaft:pruebas:listas:v1`), `v1.xml`, `v1.zip`,
  `v2.xml`, un `invalido.xml` sin UID y un `manifiesto.json` con el SHA-256 de cada
  archivo. **Si se modifica un fixture hay que actualizar su hash.**
- `esperado.json` es el resultado esperado de comparar V1 con V2: baja de
  `prueba_empresa`, alta de `prueba_empresa_nueva` y cambios en alias, documento,
  dirección, observación y relación de `prueba_persona`.
- El XSD de esos fixtures es idéntico al que usa la aplicación
  (`backend/infrastructure/listas/esquemas/sintetico_v1/lista.xsd`).
- `tests/fixtures/ofac_advanced/dos_entidades.xml` es un Advanced ficticio que cumple el
  XSD oficial; incluye un documento `Fraudulent`.
- `tests/persistencia_listas/adaptador_aceptacion_f66.py` es un lector que solo existe en
  las pruebas de F6.6: traduce hechos escritos en el XML sintético. No se registra en la
  aplicación ni prueba compatibilidad con OFAC.

**Ensayos con archivo real.** Están fijados por hash a la publicación del 2026-11-06
(ZIP `5b3a008c…726c`, XML `60698e6e…805f`). Esos bytes ya no están en `archivoslistas/`,
pero se conservan en la custodia del entorno local, ignorada por Git:
`backend/uploads/listas/5b3a008cf8311f88f26c0b6da888a1271919fd30d5dc712f24073eb77791726c` (ZIP)
y `backend/uploads/listas/60698e6e3edd49ac9398576aae7e98e06f2c0bf44cc41e485bca4732ac56805f` (XML).
No se deben borrar esos archivos si se quiere reproducir estos ensayos. Una publicación
nueva de OFAC no pasará estas pruebas sin actualizar los hashes esperados.

**En CI.** `ci.yml` ejecuta `python -m pytest -q` sin filtros. Los contratos sí corren;
las pruebas de `tests/persistencia_listas/` se **saltan** porque faltan
`LISTAS_PRUEBA_URL` y `LISTAS_PRUEBA_DIRECTORIO`, que solo define el arnés. Hoy la
persistencia, el trabajador y las migraciones del módulo no se verifican en CI.

Fallos esperados conocidos: tres `xfail` estrictos de migraciones antiguas (MIG-01–03,
[pendientes](#7-pendientes)). No cuentan como aprobados.

## 5. Resultados de referencia

Mediciones con el archivo OFAC real (publicación del 2026-11-06), hechas en una máquina de
desarrollo con PostgreSQL desechable en tmpfs y un solo trabajador. No es un SLA ni una
prueba de carga. Los archivos están en
[`arquitectura/evidencias/`](../arquitectura/evidencias/README.md) (local, no versionado).

Los resultados de las pruebas automáticas no se guardan aquí: se obtienen ejecutando la
suite (ver sección 4).

### Carga completa de OFAC

Archivo: XML de 128.630.615 bytes o ZIP de 5.777.108 bytes. Las dos cargas dan la misma
proyección (huella `57359e2a9369483a112bb5c7c8aa9bddd2421b37a26d87d9cfde0c689abc8077`).

| Dato | Valor |
|---|---|
| Sujetos | 19.563 |
| Nombres / documentos / direcciones / relaciones | 50.238 / 23.108 / 29.725 / 9.266 |
| Atributos | 1.023.351 (incluye catálogos repetidos por sujeto) |
| Lotes | 196 de 100 registros |

Cada carga incluye un SIGKILL antes del segundo lote y la espera real de la concesión.

| Medición | Desde XML | Desde ZIP |
|---|---:|---:|
| Validación | 41,6 s | 40,7 s |
| Espera tras SIGKILL | 115,7 s | 115,5 s |
| Trabajador reanudado | 704,3 s | 700,0 s |
| Total | 923,6 s | 917,7 s |
| Base de datos | 759,6 MB | 759,8 MB |
| Custodia | 128,7 MB | 134,5 MB |
| Memoria máxima del trabajador | 311 MiB | 311 MiB |

El índice `h98c01d234e5` bajó la carga desde XML de 976,0 s a 923,6 s (5,4 %). Es una sola
muestra por configuración, así que no se le puede atribuir toda la diferencia.

### Consultas sobre OFAC

Recorrido completo desde el ZIP hasta cuatro consultas: 1.011 s (16 min 51 s). La
generación de búsqueda tiene 17.651 registros consultables, 1.912 excluidos y 68.731
términos.

| Etapa | Tiempo |
|---|---:|
| Recepción del ZIP | 0,04 s |
| Validación | 42,9 s |
| Importación y sellado | 723,8 s |
| Activación | 46,5 s |
| Generación de búsqueda | 96,3 s |

| Consulta | Candidatos | Nivel | Admisión | Trabajador + PDF | PDF |
|---|---:|---|---:|---:|---:|
| R-01 nombre completo | 3 | MEDIA | 7,2 s | 18,2 s | 30 KB |
| R-02 nombre + nacimiento | 3 | MEDIA | 4,9 s | 16,5 s | 35 KB |
| R-03 alias completo | 1 | MEDIA | 4,8 s | 15,3 s | 23 KB |
| R-04 «Rosneft» | 159 | MEDIA | 5,6 s | 28,7 s | 741 KB |

R-04 muestra el costo de un nombre parcial: no se ocultan candidatos. Base al final:
831,9 MB; custodia: 135,3 MB; memoria máxima del proceso: 1,2 GiB.

## 6. Incidencias encontradas y corregidas

Sirven como aviso para quien mantenga el módulo:

| Incidencia | Corrección |
|---|---|
| El perfil OFAC admitía 256 MiB, pero la función SQL de cierre seguía en 100 MiB | Migración `f76a89b012c3`, límite solo para OFAC |
| Un trigger contaba todos los registros por cada atributo escrito (primer lote de 134 s) | `g87b90c123d4` comprueba el avance solo al cambiar controles, lotes o registros |
| Lotes de 1.000 rozaban la concesión de 120 s (79,7 s y 91,1 s desde el arranque) | Lote OFAC de 100 (perfil v2); sin ampliar la concesión |
| SIGKILL dejaba índices SQLite temporales con nombre | SQLite temporal anónimo |
| El cotejo buscaba relaciones sin índice | `h98c01d234e5` |
| Cierre de la generación con un COMMIT de más de 13 min y memoria de 5,6 GiB | `j10e23f456a7` (conteo agrupado) y lectura y verificación por bloques |
| F56-A01: la denegación de acceso a un original no dejaba registro | `RutaRecepcionAuditada` registra 401/403/404 |
| F56-A02: un usuario sin permiso recibía 503 en lugar de 403 | `PermissionError` separado de `OSError` |
| Usuario autenticado sin roles de carpeta provocaba una excepción en las rutas de listas | Ahora responde 403 |
| El seguimiento del portal se detenía tras un error de red | Sondeo cada 2 s; tras un fallo espera 4 s y luego 8 s; tras tres fallos seguidos se pausa y ofrece «Reintentar seguimiento» |
| El middleware aceptaba JWT sin `exp` | `exp` obligatorio para todo el portal |
| Tusdatos puede informar la falla de ONU con el código `onu`, y solo se reconocía `lista_onu`: la fuente habría pasado como consultada sin registros | Se reconocen los dos códigos; una prueba compara las fuentes con el catálogo de errores de Tusdatos |
| Se ignoraba `validado: false` (Tusdatos no pudo validar el documento) | El resultado lleva la advertencia `DOCUMENTO_NO_VALIDADO` y el portal la resalta |
| Una fuente que no venía en el reporte pero sí en `errores` quedaba como «no disponible» | Ahora queda como fallida |
| Un NIT inexistente (400 «Nit no encontrado») cerraba la consulta con el código técnico `SOLICITUD_RECHAZADA` | Se cierra con `DOCUMENTO_NO_ENCONTRADO` y un mensaje claro; lo mismo para la CE que no está en Migración |
| Un NIT escrito con dígito de verificación («900123456-7») se enviaba como «9001234567» | Se quita el dígito antes de enviarlo |
| Se gastaba un crédito aunque una fuente obligatoria estuviera caída en Tusdatos | Se revisa el estado de las fuentes antes de lanzar; la consulta se cierra sin gastar crédito, salvo con «Forzar actualización» |
| La recarga gratuita se gastaba de inmediato aunque la fuente con error estuviera caída; Tusdatos indica que así no sirve | Antes de recargar se revisa el estado: se espera a que la fuente vuelva y, si no vuelve a tiempo, se cierra sin gastar la recarga y diciendo que estaba caída |
| No se guardaban las capturas de pantalla que Tusdatos publica por fuente | Se custodian como evidencia `CAPTURA_PROVEEDOR` (OFAC, ONU, INTERPOL, EUROPOL, CIDOB, Procuraduría, Policía), sin credenciales hacia el host de estáticos y con el mismo permiso del PDF |
| Un NIT inexistente gastaba una consulta de listas completa antes de saberse que no existía | Se verifica antes con `verify/nit` (y la CE con `verify/ce`). Si no existe, no se consultan listas; si no está vigente, se consulta igual con aviso |
| Una CC en la caché de Tusdatos (`jobid: null`) se cerraba sin resultado | Se busca el reporte en el historial de la cuenta (`/api/v1/checks`); si no aparece, se cierra como antes |
| Una consulta que cerraba con fuentes fallidas, o sin PDF, quedaba así: nadie volvía a intentarlo aunque recargar es gratis | El trabajador revisa cada minuto las consultas cerradas de las últimas 24 h. Recarga las fuentes fallidas cuando están operativas (10 min, 1 h y 4 h; cada recarga es una consulta nueva enlazada) y vuelve a pedir el PDF y las capturas que faltaron. Nada de esto gasta crédito |
| `validate_envs.py` rechazaba `.env.dev.example` tras agregar las variables `LISTAS_*` (CI en rojo) | El validador y las tres plantillas declaran las variables nuevas |

## 7. Pendientes

### Para operar en local sin ayudas de pruebas

- Aceptación formal de F6.6: la entrega está hecha, pero la aceptación no está registrada.
- Herramienta o procedimiento soportado para registrar la fuente `ofac_sdn` y una
  política administrativa (ver 3.1).
- Pantalla de administración: hoy solo hay CLI.
- Reanudación manual de una recepción y reconstrucción forzada de versiones: tienen
  contrato, pero no ruta.
- Conciliación operativa de originales huérfanos y temporales: la ruta solo los cuenta
  y no hay limpieza.

### Antes de cualquier ambiente compartido (staging)

**Preparado en código e infraestructura (Fase 7, sin desplegar ni comprobar en el
ambiente):**

- Custodia en S3 (`LISTAS_CUSTODIA_BACKEND=s3`): informes y PDF del proveedor en el
  bucket de la aplicación bajo `listas/custodia/<sha256>`, verificados al leer y entregados
  solo por el backend. La administración de listas exige custodia local y responde 409 con S3.
- Trabajador como servicio ECS (`sagrilaft-<ambiente>-listas-worker`,
  `python -m infrastructure.listas.trabajador_servicio`): una tarea (`-c listasWorkerCount`,
  0 en bootstrap), rol propio con acceso solo a `listas/custodia/*`, logs en
  `/sagrilaft/<ambiente>/ecs/listas-worker` sin datos personales.
- Parámetros SSM `LISTAS_CUSTODIA_BACKEND`, `LISTAS_CUSTODIA_S3_PREFIJO` y
  `LISTAS_TUSDATOS_URL`, y el secreto `sagrilaft/<ambiente>/tusdatos_credentials`
  (`token`, o `usuario` y `clave` del sandbox), inyectados al backend, la migración y el trabajador.
- CDK: `-c proveedorListasCautela` acepta `simulado`/`dummy`, `externo`/`sagrilaft` y
  `deshabilitado`. Externo exige `-c habilitarNatEgress=true`; producción por defecto
  `deshabilitado` y rechaza externo y el sandbox. `-c tusdatosUrl` permite el sandbox fuera de prod.
- Roles `listas_operador` y `listas_revisor` en `keycloak/realm-sagrilaft.json` (realms
  nuevos) y `scripts/listas/crear_roles_listas_keycloak.sh` para el realm ya existente.

**Activar Tusdatos en staging** (pasos manuales, en este orden):

1. Desplegar con los cambios (los scripts de staging siguen en simulado) y comprobar que
   el trabajador arranca y que una consulta simulada se cierra con informe en S3.
2. Crear y asignar los roles con el script de Keycloak (ECS Exec en la tarea de Keycloak).
3. Rellenar `sagrilaft/staging/tusdatos_credentials`: `token` (producción de Tusdatos) o
   `usuario`/`clave` del sandbox con `-c tusdatosUrl=http://docs.tusdatos.co`. Con
   `externo` y el secreto vacío, el backend no arranca.
4. Desplegar con `-c proveedorListasCautela=externo -c habilitarNatEgress=true` (crea un
   NAT Gateway, con costo mensual) y ejecutar una consulta real de prueba.

Sigue pendiente:

- Copia y restauración coordinada de SQL y custodia. Procedimiento **propuesto**, nunca ensayado:
  1. Detener admisiones y trabajos del módulo; identificar operaciones en curso y anotar
     la revisión de Alembic y el punto de corte de la copia SQL.
  2. Copiar la base y un manifiesto de todos los objetos referenciados (originales,
     evidencias, borradores) con clave, hash y tamaño; copiar esos objetos sin
     sobrescribir y verificar el manifiesto completo.
  3. Restaurar SQL y objetos en un entorno aislado con las consultas desactivadas, y
     verificar restricciones, punteros, versiones, eventos y cada objeto. Un objeto
     faltante o corrupto impide declarar la recuperación; nunca se reconstruye un
     informe consultando de nuevo.
  4. Revisar los trabajos pendientes: los que tienen borrador continúan; los externos
     sin resultado no se repiten automáticamente. Reanudar solo después de conciliar.
- Retención del PDF del proveedor en S3 (hoy sin regla de ciclo de vida) y cifrado con
  KMS propio si Cumplimiento lo exige (hoy SSE-S3, el cifrado del bucket).
- Alarma si el trabajador se detiene o acumula consultas pendientes.
- Migraciones revisadas contra la base del ambiente y su versión de PostgreSQL.
- Rol de aplicación sin propiedad de tablas, DDL, `TRUNCATE` ni control de triggers.
- Inventario de consumidores externos de las rutas antiguas, que responden 410.
- Pruebas de persistencia del módulo integradas en CI (hoy se saltan).

### Antes de producción

- Decidir y cambiar `validar_entorno`, que hoy obliga a `deshabilitado` en producción.
- Políticas operativas aprobadas: frecuencia de comprobación y vigencia (P02,
  **propuesto**), umbrales de anomalías (P04, **propuesto**), retención y purga,
  enmascaramiento de datos por rol, responsables (titular y suplente) y auditoría
  centralizada.
- Dimensionamiento con volumen real: concurrencia, latencia, memoria, disco, WAL,
  respaldo, caída de PostgreSQL o del host.
- Calibración del buscador con un corpus representativo
  ([reglas, sección 10](BUSCADOR_REGLAS_Y_CASOS.md#10-pendiente-antes-de-usar-las-reglas-con-datos-reales)).
- Procedencia operativa de cada descarga y prueba de publicaciones nuevas de OFAC.

### Proveedor externo

Adaptador de Tusdatos implementado (Fases 2 a 5; ver
[arquitectura, sección 11](ARQUITECTURA_LISTAS.md#11-cómo-se-añade-una-fuente-o-un-proveedor)
y la guía corta [Consultas con Tusdatos](TUSDATOS.md)).
Probado con el sandbox público y con respuestas grabadas
(`tests/contracts/test_cliente_tusdatos.py`, `test_adaptador_tusdatos.py`,
`tests/persistencia_listas/test_externo_tusdatos.py`). Falta:

- Fase 5 hecha: reutilización 6 h dentro del expediente, «Forzar actualización» y
  descarga del PDF del proveedor para `listas_revisor`. Falta crear en Keycloak los roles
  `listas_*` y asignarlos (ver «Antes de cualquier ambiente compartido»).
- CC en caché (`jobid: null`): ya se intenta recuperar por `/api/v1/checks`, que el sandbox
  no tiene. Con credenciales reales falta confirmar que la consulta en caché aparece en el
  historial, el formato de `created_at` y que `check_id` es el id que recibe `report_json`.
- Códigos de `sources/status` para las fuentes de listas (OFAC, ONU, PEP, CIDOB, INTERPOL,
  EUROPOL): el catálogo `/api/fuentes-colombia` del sandbox trae los 12 códigos del sistema
  escritos igual, así que lo más probable es que coincidan. Confirmarlo con el aviso
  «sources/status no informa» del trabajador en la primera consulta real.
- Tusdatos respondió que `verify/nit` y `verify/ce` no cobran y que el 400, el 403 y las
  fallas sí (13-11-2026). Falta tenerlo por escrito.
- Preguntas abiertas para Tusdatos (cobro en 400/403/fallas, historial, códigos de estado,
  auto reintentos, retención de datos): lista completa y de dónde sale cada dato en
  [TUSDATOS.md, «Qué sabemos y de dónde sale»](TUSDATOS.md#qué-sabemos-y-de-dónde-sale).
  La propuesta comercial venció el 22-07-2026: hay que pedir una nueva.
- Preguntar a Tusdatos por el «lanzamiento de fuente puntual» que menciona la nota de
  `sources/status` (`/api/v1/sources/status/{job_id}`) y no aparece en su `openapi.json`.
- Con credenciales reales: verificar el PDF, `/api/retry` (también horas después del
  cierre, que es lo que usa la recarga automática) y la forma real de cada fuente
  (en especial los textos de Policía y los registros PEP), confirmar que
  `peps_funcion_publica` solo llega cuando hay registro y ver cómo llega `validado`.
- Alarma de CloudWatch sobre la métrica `TusdatosCreditosRestantes` (hoy solo hay aviso en
  los registros del trabajador).
- Staging (Fase 7): preparado; falta ejecutar los pasos de activación (sección
  «Antes de cualquier ambiente compartido»).
- El secreto `sagrilaft_listas_cautela_credentials` (`SAGRILAFT_API_KEY`) y
  `SAGRILAFT_API_URL` pertenecen al circuito retirado y ya no se usan para arrancar.
- El seguimiento de contratación es la tarea P15 de
  [pendientes de producción](../produccion/PENDIENTES_PRODUCCION.md#p15).

### Deuda técnica

| ID | Tema |
|---|---|
| MIG-01 | `c3f1a2b4d5e6` elimina la fecha de firma sin trasladarla (xfail) |
| MIG-02 | `c8d9e0f1a2b3` no copia contactos de órdenes y pagos (xfail) |
| MIG-03 | `b7e4f2a19c3d` no copia las listas del formulario, como los accionistas (xfail). No es un problema de OFAC |
| DEP-01 | Avisos de Pydantic (`Field` con argumentos extra, `config` de clase) |
| DEP-02 | `datetime.utcnow()` en el dummy retirado |
| DEP-03 | Avisos de Uvicorn y `websockets.legacy` |
| — | `servicios_externos/sagrilaft/deshabilitado.py` usa `ErrorConsultaListas` sin importarlo: `descargar_pdf` lanza `NameError` (código retirado) |
| — | `.env.prod.example` sugiere activar con `sagrilaft`; eso hoy impide arrancar en producción |
| — | El CDK (`infra/sagrilaft/lib/sagrilaft-stack.ts`) usa por defecto `proveedorListasCautela=sagrilaft` en prod si no se pasa el contexto; con ese valor el backend no arranca en producción. Hay que pasar siempre `-c proveedorListasCautela=deshabilitado` o corregir el valor por defecto |
| — | `.env.staging.example` sigue usando solo `PROVEEDOR_LISTAS_CAUTELA` |
| — | Retirar el circuito anterior: `domain/puertos/consultor_listas_cautela.py`, `servicios_externos/sagrilaft/`, `ServicioVerificacionSagrilaft`, `ListaCautelaService`, `proveedores_simulados.py` y la ruta `/api/expedientes/sagrilaft/disponibilidad` |
