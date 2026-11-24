# Pendientes de producción

Lista única de tareas de SAGRILAFT. Cada tarea tiene un código (P01, P02…) que no
cambia: los demás documentos enlazan el código en vez de copiar su estado.

- Estado de los ambientes: [Estado](../estado/ESTADO_DESPLIEGUE_STAGING_PROD.md).
- Cómo se hace algo: [guía de despliegue](despliegue/GUIA_DESPLIEGUE_LOCAL.md) o [runbook](../operacion/RUNBOOK_OPERATIVO.md).
- Valores de configuración: [Configuración en AWS](configuracion/MATRIZ_AWS_CONFIG.md).

Revisado el 2026-11-24. Los datos de AWS son los verificados el 2026-11-23.

Para cerrar una tarea: anotar fecha, ambiente y evidencia, y pasarla a la
[tabla de cierres](#cierres) sin cambiar su código.

<a id="corte"></a>
## 1. Antes de abrir producción

<a id="p01"></a>
### P01 — Tag y notas de versión

**Estado:** 🟡 Parcial.

Las releases se hacen y se verifican con `deploy_release.py`. Falta crear el tag
(`vX.Y.Z`) sobre el SHA que se apruebe en el Go (hoy `972f993`) y escribir sus notas en
un `CHANGELOG.md`, que todavía no existe ([guía](despliegue/GUIA_DESPLIEGUE_LOCAL.md#release)).
El repositorio no tiene ningún tag.

<a id="p02"></a>
### P02 — Go final de apertura

**Estado:** 🟡 Parcial.

Están definidos quién decide, los criterios, los riesgos aceptados y cómo volver atrás
([registro P02](despliegue/P02_GO_NO_GO_ROLLBACK.md)). Falta el acta del Go final firmada
por Andrés Hurtado, con el SHA, la fecha, los riesgos aceptados y el resultado de cada
criterio. El Go del 2026-10-06 solo autorizó empezar el corte, no abrir a usuarios.

<a id="p05"></a>
### P05 — Firma automática en producción

**Estado:** 🔴 Bloqueado: la cuenta de Zoho Sign no tiene créditos de API.

El único intento en producción (2026-11-03, 17:09 UTC) lo rechazó Zoho con `code 12000`
(«Compre créditos de Zoho Sign para enviar documentos a través de la API»). Desde
entonces no hubo más intentos ni llamadas al webhook. Ese intento probablemente dejó un
borrador en Zoho ([P16](#p16)). El saldo de créditos no se pudo consultar: hay que
revisarlo en la consola de Zoho.

Para cerrar: con créditos, firmar un expediente de prueba y comprobar que el webhook lo
pase a `FIRMADO` sin intervención, con el PDF firmado en S3 y la auditoría registrada.
En staging ya funciona ([runbook](../operacion/RUNBOOK_OPERATIVO.md#zoho)).

<a id="p06"></a>
### P06 — Alarmas probadas de punta a punta

**Estado:** 🟡 Parcial.

Producción tiene 16 alarmas, todas en `OK` el 2026-11-23, que avisan por SNS a un solo
correo confirmado. La ruta CloudWatch → SNS → correo se probó el 2026-10-07 forzando el
estado de una alarma. Falta:

1. Decidir si se agregan más destinatarios. Los once de la lista original se retiraron
   el 2026-10-21 porque nunca confirmaron; volver a incluirlos requiere autorización
   ([destinatarios](configuracion/MATRIZ_AWS_CONFIG.md#destinatarios)).
2. Provocar una alarma con una métrica real y comprobar que el aviso llegue en menos de
   cinco minutos, o aceptar el riesgo por escrito en el Go.

<a id="p07"></a>
### P07 — Prueba funcional y de correo en producción

**Estado:** 🔴 Pendiente.

Hacer un recorrido completo con datos ficticios: crear un acceso, recibir el correo
(Gmail y Outlook), guardar, subir adjuntos y usar la IA, radicar, devolver, corregir,
aprobar, firmar y cerrar. Comprobar inicio de sesión y roles, y que no haya errores.
Archivar la evidencia aparte de la de staging. El
[recorrido de staging](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md) sirve
de guía.

Los usuarios internos y sus roles ya están creados en el Keycloak de producción (revisado
el 2026-10-27 en la consola). Antes de ejecutar esta prueba hay que resolver [P21](#p21).

<a id="p21"></a>
### P21 — Datos de prueba en producción

**Estado:** 🔴 Requiere decisión antes de abrir (registrado el 2026-11-23).

El bucket de producción tiene 29 objetos de pruebas hechas el 30 y 31 de octubre, el
3 de noviembre y el 18 de noviembre, en carpetas de clientes y proveedores; una lleva el
nombre de una empresa. No se revisó el contenido de la base ni de los archivos. La copia
`sagrilaft-prod-base-pre-pruebas-20261123` se tomó **después** de esas pruebas, así que
también los contiene: no es una base limpia.

Hay que decidir:

1. Si son datos ficticios o de personas y empresas reales (en ese caso también es un
   tema de protección de datos).
2. Si se limpian, con un procedimiento que trate la base y S3 juntos (los triggers de
   auditoría impiden borrar ciertas filas), o si se conservan marcados como prueba.

No existe procedimiento de limpieza; escribirlo es parte de esta tarea.

## 2. Operación

<a id="p09"></a>
### P09 — Ver actuar el autoescalado

**Estado:** 🟡 No bloqueante.

En la prueba de carga de staging no se llegó al umbral, porque el límite de peticiones
por IP frenó el tráfico ([runbook](../operacion/RUNBOOK_OPERATIVO.md#historial)). Queda
observarlo con carga desde varios orígenes o en un pico real.

<a id="p10"></a>
### P10 — Ensayar la restauración en producción

**Estado:** 🟡 Pendiente; riesgo aceptado en [P02](despliegue/P02_GO_NO_GO_ROLLBACK.md#riesgo-rds).

Restaurar una copia de producción en una instancia temporal, comprobar los datos, medir
el tiempo y borrar solo la temporal ([procedimiento](../operacion/RUNBOOK_OPERATIVO.md#restauracion)).
Keycloak usa la misma base, así que una restauración también devuelve usuarios y sesiones
al momento de la copia.

## 3. Mejoras y verificaciones externas

<a id="p11"></a>
### P11 — GitHub sin acceso a AWS

**Estado:** 🟡 Parcial. Solo falta borrar un ambiente vacío, y no bloquea nada.

El CI ya no entra a AWS: solo corre pruebas ([qué revisa](despliegue/GUIA_DESPLIEGUE_LOCAL.md#ci)).
Antes publicaba imágenes con el rol compartido `GithubActionsOIDC-DeployRole`, que acepta
cualquier repositorio de la organización y tiene permisos de más, y fallaba desde el 18 de
noviembre porque ese rol no lee SSM. El cambio se unió a `main` el 2026-11-24 (PR #3), y
el CI de `main` volvió a verde.

Limpieza en GitHub del 2026-11-24:

- Se borraron las variables `AWS_ROLE_TO_ASSUME`, `AWS_ACCOUNT_ID`, `HOSTED_ZONE_ID` y
  `CERTIFICATE_ARN`. El secreto `ALERTAS_STAGING` no existía.
- Se borraron los secretos `VITE_KEYCLOAK_CLIENT_ID`, `VITE_KEYCLOAK_REALM`,
  `VITE_KEYCLOAK_URL` y `VITE_PORTAL_INTERNO_URL`, de junio de 2026. Ningún workflow los
  usó nunca: las imágenes toman esos valores de SSM o del `.env` del ambiente.
- Falta borrar el ambiente `production` de *Settings → Environments*. Lo creó solo el CI
  anterior, que lo mencionaba; está vacío y el CI nuevo no lo vuelve a crear. Borrarlo
  requiere ser administrador del repositorio.

El rol compartido no se toca en AWS: lo pueden usar otros repositorios. Si más adelante se
quiere publicar en staging desde GitHub, hay un rol propio preparado, limitado a staging
([pasos](../../infra/sagrilaft/policies/github-staging/README.md)).

<a id="p12"></a>
### P12 — Proteger las ramas `dev` y `main`

**Estado:** 🔴 Sin protección (verificado el 2026-11-23: `branches/main/protection` responde 404 y no hay rulesets). `dev` existe desde el 2026-11-24.

Un administrador del repositorio debe proteger las dos ramas del
[flujo](despliegue/GUIA_DESPLIEGUE_LOCAL.md#ramas): exigir PR, al menos una revisión y las
cuatro revisiones del CI en verde. Se puede hacer en *Settings → Branches* o con:

```bash
for rama in dev main; do
gh api -X PUT repos/ai-scm/Sagrilaft/branches/$rama/protection --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Secretos (gitleaks)", "Backend", "Frontend", "Infraestructura"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1 },
  "restrictions": null
}
JSON
done
```

Los nombres deben coincidir con los de los jobs de `ci.yml`. Si cambian, hay que cambiarlos
aquí también.

También en *Settings → General*: dejar `dev` como rama por defecto, para que los PR nuevos
apunten ahí, y activar *Automatically delete head branches*, para que GitHub borre la rama
al unir su PR.

<a id="p14"></a>
### P14 — Caso de uso de SES ante AWS

**Estado:** 🔴 Abierto; no bloquea.

El caso de uso registrado ante AWS para la cuenta tiene la URL y la descripción de otro
proyecto. Hay un ticket con el administrador de la cuenta compartida. Falta que lo
actualice y guardar la confirmación.

<a id="p15"></a>
### P15 — Activar la consulta de listas

**Estado:** 🔴 Diferido; no bloquea la apertura si Cumplimiento lo acepta.

El adaptador de Tusdatos existe y está desplegado desde `d4cdb84`. Para activarlo en
producción falta:

1. El contrato con Tusdatos (la propuesta comercial venció el 2026-07-22).
2. Credenciales reales en `sagrilaft/prod/tusdatos_credentials`, hoy vacío.
3. Un cambio de código: `configuracion.py` rechaza en producción cualquier modalidad
   distinta de `deshabilitado`.

**Sin confirmar:** si Cumplimiento aprobó por escrito operar sin consulta de listas
mientras tanto. Es un riesgo de cumplimiento, no técnico. Lo pendiente del módulo está
en [Operación de listas](../listas/OPERACION_PRUEBAS_Y_PENDIENTES.md#7-pendientes).

<a id="p16"></a>
### P16 — Borradores huérfanos en Zoho

**Estado:** 🔴 Limitación aceptada.

Si Zoho crea el borrador pero falla el envío, el sistema no guarda el `request_id` y no
puede cancelarlo ([detalle](../operacion/RUNBOOK_OPERATIVO.md#huerfanos)). Ya hay al menos
uno, del 2026-11-03.

<a id="p17"></a>
### P17 — Ampliar la documentación técnica

**Estado:** 🔴 Mejora no bloqueante.

Documentar el modelo de datos, el contrato HTTP y la arquitectura del frontend (React,
Keycloak, Axios).

<a id="p18"></a>
### P18 — Evidencia complementaria de staging

**Estado:** ⚪ Sin evidencia suficiente.

Falta acreditar que se invalidaron todos los accesos de prueba. Si la evidencia se va a
compartir fuera del equipo, hacer copias anonimizadas: las capturas y el PDF de
[staging](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md) tienen datos
sensibles. No se modifican los originales.

<a id="p19"></a>
### P19 — Más pruebas automáticas en CI

**Estado:** 🟡 Parcial.

El CI corre las pruebas del backend, del formulario público y de infraestructura, y
compila los dos frontends. Faltan: pruebas contra PostgreSQL (las de persistencia de
listas se saltan), pruebas propias del portal interno y las de navegador (Playwright). Los huecos están en el
[catálogo de pruebas](../../tests/README.md#cobertura) y los comandos en el
[README del arnés](../../tests/integration/README.md).

<a id="cierres"></a>
## 4. Cerrado

<a id="p03"></a><a id="p04"></a><a id="p08"></a><a id="p13"></a>

| Tarea o decisión | Fecha y alcance | Evidencia |
|---|---|---|
| P03 — Configuración de producción | 2026-10-20: secretos de SMTP y Zoho conciliados con `.env.prod`; 2026-10-27: DNS, TLS, SSM, S3 y Bedrock responden desde el contenedor del backend | [Configuración en AWS](configuracion/MATRIZ_AWS_CONFIG.md) |
| P04 — Primer despliegue de producción | 2026-10-21, `f8d9dcf`; el lock que quedó tomado se liberó el 2026-10-24 | [Evidencia del primer corte](../evidencia/primer-corte-prod-20261021/README.md) |
| P08 — HSTS y consola de Keycloak | 2026-10-21: HSTS en los tres dominios. 2026-10-24: regla de WAF para `/admin` y `/realms/master`, probada en staging | [Evidencia del primer corte](../evidencia/primer-corte-prod-20261021/README.md); regla en `cortafuegos-web.ts` |
| P13 — CDK Diff en CI | 2026-11-24: retirado en la rama `ci/ci-basico-sin-aws`, porque necesitaba leer toda la cuenta de AWS. El diff se hace a mano y se pega en el PR | [Guía](despliegue/GUIA_DESPLIEGUE_LOCAL.md#infraestructura) |
| P20 — Eliminado a pedido del usuario | 2026-11-23 | — |
| Flujo completo en staging, con firma, auditoría y cierre | 5 y 6 de octubre | [E2E](../evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md) |
| Migraciones desde cero en PostgreSQL | 1 de octubre | [Validación local](../evidencia/e2e-staging/VALIDACION_STAGING_E2E.md) |
| Simulacros de staging (carga, restauración, alarmas, Zoho, SES) | Septiembre y octubre | [Runbook, historial](../operacion/RUNBOOK_OPERATIVO.md#historial) |
| Pruebas del backend obligatorias en CI | 19 de septiembre | [Workflow](../../.github/workflows/ci.yml) |
| Volumen acordado con negocio | 27 de septiembre: unas 100 contrapartes al mes | Decisión registrada |
