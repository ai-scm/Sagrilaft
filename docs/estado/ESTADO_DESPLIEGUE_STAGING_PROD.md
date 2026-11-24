# Estado de staging y producción

Qué corre en cada ambiente y cómo se comprobó. Las tareas abiertas están en
[Pendientes](../produccion/PENDIENTES_PRODUCCION.md) y la forma de desplegar, en la
[guía de despliegue](../produccion/despliegue/GUIA_DESPLIEGUE_LOCAL.md).

## Producción — verificado el 2026-11-23

Comprobado ese día con consultas de solo lectura a AWS, `/health` y git, después de la
release de la tarde. Si pasó tiempo, hay que volver a mirar antes de decidir algo.

**Activa, pero sin abrir a usuarios reales.** Faltan el Go final (P02) y las pruebas
P05, P06 y P07 ([Pendientes](../produccion/PENDIENTES_PRODUCCION.md#corte)).

| Componente | Estado | Cómo se comprobó |
|---|---|---|
| Versión | `972f99312050e13e759b1d6d8562d7707386c7d9` (release del 2026-11-23) | `/health` y definiciones de tarea de ECS |
| Esquema de la base | Revisión Alembic `n54c67d890eb` (la release del 23-nov no la cambió) | Registro de la release (`release_execute.log`) |
| Stack `SagrilaftStack-prod` | `UPDATE_COMPLETE` | `describe-stacks` |
| Servicios ECS | Backend, formulario, portal y Keycloak con 1 tarea cada uno. El trabajador de listas existe desde el 2026-11-18 y está en 0 | `describe-services` |
| Backend | 2 GB de memoria desde el 2026-11-23; escala solo entre 1 y 2 copias | Definición de tarea `backend:8` y `describe-scalable-targets` |
| Base de datos | `db.t3.small`, PostgreSQL 16.13, una sola zona, 14 días de copias automáticas, cifrada, no pública, con protección contra borrado | `describe-db-instances` |
| Copias manuales | `sagrilaft-prod-base-pre-pruebas-20261123` y `sagrilaft-prod-pre-ip-cliente-20261123` | `describe-db-snapshots` |
| Lock de despliegue (S3) | Libre | `head-object` sin objeto |
| Alarmas | 16, todas en `OK`. Avisan por SNS cuando fallan y cuando se recuperan | `describe-alarms` |
| Destinatarios de alertas | Una suscripción de correo, confirmada | `list-subscriptions-by-topic` |
| IP real del cliente | `TRUSTED_PROXY_IPS=10.0.0.0/16`. Dos intentos de prueba quedaron registrados con la IP real | Parámetro SSM y registros del backend |
| Proveedor de listas | `deshabilitado` (el código no permite otro valor en producción) | Parámetro SSM y `backend/infrastructure/config/configuracion.py` |
| Firma con Zoho | Ninguna firma en producción. El único intento (2026-11-03 17:09 UTC) lo rechazó Zoho por falta de créditos de API. El webhook nunca ha recibido una llamada | Registros del backend (se guardan 30 días) |
| Tags de versión en git | Ninguno | `git tag` y `git ls-remote --tags` |

### Releases de producción

Sacado de las definiciones de tarea del backend en ECS.

| Fecha | Versión | Evidencia |
|---|---|---|
| 2026-10-07 | Creación del stack, con imagen provisional y servicios en 0 | No se conservó; queda el registro de CloudFormation ([detalle](../evidencia/README.md#bootstrap-prod-20261007)) |
| 2026-10-21 | `f8d9dcf`: primer corte, migración a `f8a9b0c1d2e3` | [Recuperada](../evidencia/primer-corte-prod-20261021/README.md) |
| 2026-10-30 | `58125cb`: corrige el arranque de nginx en los frontends | Sin evidencia archivada ([detalle](../evidencia/README.md#sin-evidencia)) |
| 2026-11-03 | `84ca98e`: mensaje claro cuando Zoho no tiene créditos | Sin evidencia archivada ([detalle](../evidencia/README.md#sin-evidencia)) |
| 2026-11-18 | `d4cdb84`: adaptador de listas y migración a `n54c67d890eb` | `tmp/despliegue-prod-20261118/` (fuera de git) |
| 2026-11-23 | `972f993`: IP real del cliente y 13 alarmas nuevas, sin migración | `tmp/despliegue-prod-20261123/RESUMEN.md` (fuera de git) |

Cambios de infraestructura sin imagen nueva: etiquetado y autoescalado (2026-11-18);
2 GB de memoria para el backend y 14 días de copias (2026-11-23).

## Staging — verificado el 2026-11-23

**Apagado** desde el 2026-11-23: servicios en 0 y base detenida (`describe-services`,
`describe-db-instances`). Última release: `02d3ea9` (2026-11-23), con la que se probaron
la IP real y las alarmas antes de llevarlas a producción
(`tmp/ip-cliente-staging-20261123/RESUMEN.md`). Base `db.t4g.small` con 7 días de copias.
Usa listas simuladas (`dummy`) y tiene el trabajador de listas desde el 2026-11-17. Se
enciende y se apaga con `scripts/aws/staging_encendido.sh`.

## Decisiones de operación vigentes

- El despliegue con CDK se hace a mano (decisión del 2026-09-29).
- Producción sale con las listas deshabilitadas hasta contratar un proveedor. Lo que
  falta para activarlas está en [P15](../produccion/PENDIENTES_PRODUCCION.md#p15).
- El riesgo de que Outlook marque correos como spam se aceptó el 2026-10-06
  ([P02](../produccion/despliegue/P02_GO_NO_GO_ROLLBACK.md#riesgo-outlook)).

Los registros anteriores al 2026-11-23 (puesta en marcha de staging, primer corte,
conciliación de secretos de octubre) están en el historial de git de este archivo y en
la [evidencia](../evidencia/README.md).
