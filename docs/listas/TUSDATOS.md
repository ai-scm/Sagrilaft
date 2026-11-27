# Consultas de listas con Tusdatos

Esta guía explica cómo funciona la consulta de listas cuando el módulo trabaja con
Tusdatos (la modalidad «externa»). Está pensada para quien revisa los resultados o
atiende la operación. El detalle técnico está en la
[arquitectura, sección 11](ARQUITECTURA_LISTAS.md#11-cómo-se-añade-una-fuente-o-un-proveedor).

Revisada contra el código el 24-11-2026. En AWS el adaptador está desplegado, pero
ninguno de los dos ambientes tiene credenciales: producción no permite esta modalidad
([P15](../produccion/PENDIENTES_PRODUCCION.md#p15)) y staging usa listas simuladas.

## Qué se consulta

Tusdatos busca por **número de documento**. Se aceptan cuatro tipos:

| Documento | Qué hace falta |
|---|---|
| Cédula de ciudadanía (CC) | El número. La fecha de expedición es opcional: con ella Tusdatos valida que coincida y consulta fuentes adicionales |
| Cédula de extranjería (CE) | El número y la fecha de expedición |
| Pasaporte | El número y el nombre completo |
| NIT | Solo el número, sin dígito de verificación (si se escribe «900.123.456-7», el sistema quita el «-7») |

Si falta algo, el portal rechaza la consulta antes de enviarla y no se gasta ningún
crédito. El nombre solo se pide y se envía con el pasaporte; en los demás casos Tusdatos
resuelve el nombre por su cuenta. País del documento y fecha de nacimiento no se piden:
Tusdatos no los usa (siguen en la búsqueda simulada).

Desde el 2026-11-27, en modo Tusdatos el portal tiene un solo botón, «Generar reporte»: el
equipo escribe a mano el tipo y el número de documento (y la fecha de expedición o el nombre
cuando aplican); no se precarga nada del expediente. Antes de consultar se muestra un resumen
de los datos para verificarlos y confirmar. Cada reporte consulta un solo documento; para la
contraparte y el representante legal se generan dos reportes. El historial muestra el
documento consultado. La búsqueda por archivos y la simulada conservan sus dos botones.

## Qué fuentes se revisan

Solo las aprobadas para SAGRILAFT. El resto de lo que trae el reporte de Tusdatos
(Sisben, RUAF, FOSYGA, tránsito, etc.) se descarta antes de guardar nada.

| Fuente | Persona | Empresa (NIT) |
|---|:---:|:---:|
| OFAC (Lista Clinton), por documento | ✓ | ✓ |
| OFAC, por nombre | ✓ | |
| Consejo de Seguridad de la ONU | ✓ | ✓ |
| INTERPOL | ✓ | |
| EUROPOL | ✓ | |
| Listas y PEP, por documento | ✓ | ✓ |
| Listas y PEP, por nombre | ✓ | ✓ |
| Listas y PEP, función pública (Colombia) | ✓ | |
| CIDOB, PEP a nivel mundial | ✓ | |
| Procuraduría General de la Nación | ✓ | ✓ |
| Contraloría General de la República | ✓ | ✓ |
| Policía Nacional | ✓ | |

Las listas restrictivas, las vinculantes y los PEP internacionales no son fuentes
aparte: vienen dentro de los registros de «Listas y PEP». Cada registro lleva su
categoría para que el revisor la vea.

## Cómo leer el resultado

Desde el 2026-11-25 Tusdatos tiene su propio formato de resultado (`tusdatos-1`, en
`backend/domain/listas/contratos_tusdatos.py`), separado del de la búsqueda propia sobre
archivos de listas: una entrada por fuente con su estado, sus registros con el detalle tal
como lo publica la fuente (sin aplanar ni recortar), los códigos de hallazgo que Tusdatos
asoció y, en PEP, la versión de la base y el resumen de listas si vienen. No lleva versiones
fijadas, hashes, puntajes ni motivos de comparación, que son de la búsqueda por archivos.
Cada registro se guarda como una coincidencia revisable. Las consultas anteriores conservan
el formato 2.0.

Cada fuente queda en uno de estos estados:

- **Con registro:** Tusdatos la revisó y encontró al menos un registro. Todos quedan en
  la fuente, también los que solo vienen marcados (ONU, INTERPOL, Contraloría) o como
  frase (Policía).
- **Sin registro:** Tusdatos la revisó y no encontró nada.
- **No consultada:** Tusdatos no pudo consultarla. Se intenta una vez más, sin costo; si
  sigue fallando, la consulta no puede concluir. Si Tusdatos dice que la fuente está
  caída, el sistema espera a que vuelva antes de intentarlo. Si no vuelve a tiempo, la
  fuente queda con el motivo «caída o en mantenimiento».
- **No incluida:** la fuente no vino en el reporte, por ejemplo porque no está en el
  plan contratado.

Los nombres de las fuentes y las descripciones de los hallazgos salen de los catálogos
oficiales de Tusdatos, guardados en `backend/infrastructure/listas/tusdatos/catalogos/`.
OFAC, ONU, INTERPOL, EUROPOL y PEP por función pública no tienen modelo publicado: su
detalle se muestra tal como llega y queda marcado como estructura no documentada.

Con eso, la consulta termina así:

- **Completada, sin candidatos:** todas las fuentes obligatorias se revisaron y no hubo
  registros.
- **Completada, con candidatos:** hay registros para revisar. Un candidato es una
  alerta, no una decisión: alguien tiene que confirmar si se trata de la misma persona.
  Cada registro se revisa por separado.
- **Parcial o no concluyente:** faltó alguna fuente obligatoria o pasó algo que impide
  afirmar que no hay registros. Hay que repetir la consulta o revisarla a mano.

Casos especiales:

- **PEP por función pública** solo viene en el reporte cuando hay un registro. Por eso,
  si no aparece, no impide concluir. Si aparece con error, sí lo impide. Esta regla se
  confirmará cuando haya credenciales reales.
- **Documento no validado:** a veces Tusdatos avisa que no pudo validar el documento
  contra la fuente oficial (por ejemplo, la cédula no coincide con la Registraduría). El
  portal lo muestra en rojo. Un «sin candidatos» con este aviso no es confiable:
  conviene revisar el número y el tipo de documento antes de darlo por bueno.

- **Documento no encontrado:** si Tusdatos responde a la consulta que no encontró el
  documento (por ejemplo, un NIT fuera del registro mercantil), la consulta se cierra con
  ese mensaje para que se revise el número antes de repetirla.

## Sin verificación previa del documento

Hasta el 2026-11-25, antes de consultar un NIT o una cédula de extranjería se llamaba a
`verify/nit` o `verify/ce`. Se retiró: no hace falta para consultar listas y no estaba
confirmado por escrito que no cobrara. Un documento inexistente lo informa la propia
consulta. Las consultas viejas pueden conservar el aviso «Documento no vigente».

El nivel de riesgo que calcula Tusdatos (alto, medio, bajo) se muestra solo como
referencia. Ese nivel depende de cómo esté configurada la cuenta en Tusdatos y no es
una decisión de cumplimiento.

## Créditos y consultas repetidas

Cada consulta nueva en Tusdatos gasta un crédito. Para no gastar de más:

- Si el mismo documento ya se consultó **en el mismo expediente** en las últimas
  6 horas, el portal muestra esa consulta en lugar de hacer otra.
- Esta regla no cruza expedientes. Con cédulas, Tusdatos tampoco cobra si se repiten
  dentro de 6 horas.
- Para hacer una consulta nueva de todos modos existe el botón **«Forzar
  actualización»**. Solo lo ve el equipo revisor y pide confirmación.

Antes de cada consulta nueva, el sistema pregunta a Tusdatos (sin costo) dos cosas:

- **¿Hay fuentes caídas?** Si una de las fuentes que deciden el resultado está caída o
  en mantenimiento, la consulta no se hace: se cierra con un mensaje que dice cuál, y no
  se gasta crédito. Se puede intentar más tarde o usar «Forzar actualización» para
  consultar de todos modos, sabiendo que el resultado quedará parcial. Si Tusdatos no
  responde a esta pregunta, la consulta sigue normalmente.
- **¿Cuántos créditos quedan?** El saldo se publica como métrica
  (`TusdatosCreditosRestantes`) y, si baja de 100, queda un aviso en los registros. El
  umbral se cambia con `LISTAS_TUSDATOS_ALERTA_CREDITOS`. Esto nunca bloquea una consulta.

En el sandbox esta revisión no se hace: allí el estado de las fuentes es fijo
(Procuraduría aparece siempre en mantenimiento) y los créditos siempre son cero.

Para NIT y cédula de extranjería hay además una tercera revisión, la del documento
(ver «Verificación del NIT y de la cédula de extranjería»). Esa no se sabe si cobra.

Si la cédula ya se había consultado en las últimas 6 horas, Tusdatos no la repite ni la
cobra, pero tampoco dice dónde está el reporte. El sistema lo busca en el historial de la
cuenta y sigue con ese. Si no lo encuentra, la consulta se cierra con un aviso que sugiere
«Forzar actualización».

Una consulta que se envió a Tusdatos pero cuya respuesta se perdió (caída de red,
reinicio del servidor) queda **indeterminada** y no se repite sola, porque pudo haber
gastado el crédito. Hay que revisarla y, si hace falta, forzar una nueva.

## Evidencias

- **Informe interno:** lo genera el sistema con lo encontrado. Lo descarga cualquiera
  que vea el historial.
- **PDF de Tusdatos:** es el reporte oficial del proveedor. Trae datos de todas sus
  fuentes, no solo de las de SAGRILAFT, así que solo lo descarga el equipo revisor y cada
  descarga queda registrada.
- **Capturas de pantalla:** para OFAC (por documento y por nombre), ONU, INTERPOL,
  EUROPOL, CIDOB, Procuraduría y Policía, Tusdatos publica una foto de la página de la
  fuente tal como la vio al consultar. El sistema guarda una por fuente de la consulta,
  con su huella, junto al PDF. Sirven de prueba si alguien pregunta qué mostraba la
  fuente ese día. Las ve el mismo equipo que ve el PDF y cada descarga queda registrada.
  No cuestan crédito. Si alguna no está, la consulta se cierra igual. Para apagarlas,
  `LISTAS_TUSDATOS_CAPTURAS=false`. Listas y PEP no tiene captura: su evidencia es el
  registro que trae el reporte.

## Tiempos

Una consulta tarda en promedio un minuto. Si en 15 minutos Tusdatos no responde, la
consulta se cierra como no concluyente. Entre una consulta y la siguiente el sistema
espera 5 segundos, como pide Tusdatos.

## Lo que quedó incompleto se recupera solo

Dentro de esos 15 minutos el sistema ya reintenta una vez, gratis, las fuentes que
fallaron. Si aun así la consulta cierra incompleta, el trabajador la sigue mirando
durante 24 horas y recupera lo que falte sin gastar crédito:

- **Fuentes que fallaron.** A los 10 minutos, a la hora y a las 4 horas del cierre
  pide a Tusdatos que vuelva a consultar esas fuentes (`/api/retry`, que no cobra). Antes
  revisa que estén operativas: si siguen caídas, espera a la siguiente vuelta. Cada
  recarga es **una consulta nueva** en el historial, marcada «recarga automática» y
  enlazada a la anterior. La anterior no se toca: lo que el revisor ya vio queda igual.
  El resultado nuevo trae un aviso que dice de qué consulta viene y que no costó crédito.
- **PDF y capturas que no llegaron.** Se vuelven a pedir en esos mismos tiempos y se
  suman como evidencia a la misma consulta. Las capturas solo se vuelven a pedir si no se
  alcanzaron a pedir antes del cierre; si Tusdatos dijo que no había, no se insiste.

No se recarga si alguien ya volvió a consultar ese documento en el expediente, si
Tusdatos rechaza la recarga (se deja de insistir) ni después de tres intentos. Lo que
gasta crédito (una consulta que no alcanzó a enviarse, o que quedó indeterminada) no se
repite solo: lo decide una persona. Para apagar todo esto,
`LISTAS_TUSDATOS_RECUPERAR=false`.

## Qué sabemos y de dónde sale

Revisado el 13-11-2026 contra dos documentos: la documentación de la API
(`openapi.json`, publicada en https://docs.tusdatos.co/redoc) y la propuesta comercial
«Cumplimiento 360» que envió Tusdatos. Lo que no aparece en ninguno de los dos queda
como «no documentado»: no se da por cierto hasta que Tusdatos lo confirme por escrito o
lo veamos con credenciales reales.

**Confirmado en la documentación**

| Dato | Dónde está |
|---|---|
| Cada consulta (`launch`) en producción gasta un crédito | `/api/launch`: «Cada petición realizada a este endpoint en producción, consume créditos» |
| Una cédula de ciudadanía repetida dentro de 6 horas no se cobra (sin `force`) | `/api/launch`, mismo texto. Solo lo dice para CC |
| `force: true` solo sirve para cédula de ciudadanía | `/api/launch`, ejemplo 127: «válido únicamente para este tipo de documento» |
| 5 segundos entre una consulta y la siguiente | `/api/launch` |
| El reintento de fuentes con error no gasta crédito | `/api/retry`: «sin descontar consultas del plan» |
| Reintentar con la fuente caída no sirve; hay que esperar | `/api/v1/sources/status`, tabla de estados: «Un reintento inmediato suele ser inútil» |
| Revisar el estado de las fuentes y el saldo no gasta crédito | `/api/v1/sources/status` («no consume créditos») y `/api/plans` |
| En la validación de PPT, la fecha incorrecta o el PPT no registrado sí se cobran | `/api/launch/verify/ppt`. Solo lo dice para PPT |

**Confirmado en la propuesta comercial**

| Dato | Dónde está |
|---|---|
| El plan ofrecido es «Cumplimiento 360», un paquete de 1.000 consultas | Página «Inversión» |
| El plan trae listas, antecedentes completos, validación detallada y reputacional. Rucom, ADRES (Fosyga), reputacional avanzado y CONTE cuestan aparte | Páginas «Nuestras fuentes» y «Fuentes adicionales» |
| Las consultas compradas se pueden usar hasta 2 años | «Términos y condiciones» |
| Si una falla externa impide consultar el 30 % o más de las fuentes, devuelven la parte proporcional | «Alcance del servicio» |
| Soporte de lunes a viernes, de 8:30 a. m. a 5:30 p. m. | «Alcance del servicio» |
| Para activar el servicio piden la política de tratamiento de datos personales de la empresa (Ley 1581) | Última página |
| El plan incluye «auto reintentos de fuentes» y monitoreo semanal de listas y PEP durante un año | «Servicios agregados» y «Valor agregado» |
| La propuesta vencía el 22-07-2026 | Portada y página de aceptación |

Como la propuesta ya venció, el precio y las condiciones hay que pedirlos de nuevo.

**Visto con credenciales reales** (25-11-2026, cuenta de cortesía con 5 consultas)

| Dato | Cómo se vio |
|---|---|
| El usuario y la clave del portal sirven para la API (Basic Auth). El correo se escribió en minúsculas | `GET /api/plans/` respondió 200 |
| Crear API Tokens no está habilitado para nuestro cliente: hay que pedírselo a Tusdatos antes de producción | `POST /api/v1/auth/token` respondió 403 «El acceso a API Tokens no está disponible para tu cliente» |
| Producción exige la barra final en `/api/plans/` y `/api/v1/checks/` (sin ella responde 308). El sandbox hace lo contrario (307 hacia la ruta sin barra). El cliente sigue solo esas redirecciones, en el mismo host | Sondeo de rutas sin costo |
| `sources/status`, `results` y `report_json` responden sin redirección. `report_pdf` y `report_nit_pdf` dan 410 con un id inexistente | Mismo sondeo, con identificadores falsos |
| `/api/plans` responde una lista (una fila por compra) con `amount`, `purchase_amount` y `demo`; el sandbox, un objeto | `GET /api/plans/` |
| Si `/api/launch` también redirige no se pudo ver sin gastar: el cliente lo cubre igual | Pendiente de la primera consulta |

Tusdatos informó después que una cuenta demo no tiene API Token ni consultas por API: las 5 consultas de cortesía solo se usan en su portal web. Lo de arriba sigue sirviendo para cuando se contrate el plan.

**Respuestas de Tusdatos pendientes de tener por escrito** (13-11-2026)

- `verify/nit` y `verify/ce` no cobran crédito (ya no se usan: se retiraron el 2026-11-25).
- El documento inexistente (400), el titular que no autoriza (403) y la consulta con
  todas las fuentes en error sí cobran. Es la razón de revisar las fuentes caídas antes
  de lanzar.

Mientras no estén por escrito, se tratan como probables, no como seguras.

**No documentado (hay que preguntarlo)**

- Si se cobra al repetir dentro de 6 horas una cédula de extranjería, un pasaporte o un
  NIT. La regla de las 6 horas solo se menciona para la cédula de ciudadanía.
- Qué fuentes adicionales consulta Tusdatos cuando una CC lleva fecha de expedición, y si
  una fecha que no coincide hace fallar o cobrar la consulta (solo está documentado para PPT).
- Si la consulta servida desde la caché de 6 horas aparece en el historial
  (`/api/v1/checks`), si `check_id` es el mismo id que recibe `report_json` y en qué formato
  viene `created_at`. El esquema solo dice que son textos, y el ejemplo de la página web
  está relleno con «string». Ojo: `issued_date` es la fecha de expedición del documento;
  la de la consulta es `created_at`, que es la que usa el sistema.
- Cómo se envían `country` y `document_type` al historial. La documentación los marca como
  parámetros de ruta, pero la ruta escrita los pone después del `?`. El sistema los envía
  como `?country=CO&document_type=CC`. En el sandbox las dos formas responden 404, porque
  allí el historial no existe.
- Con qué códigos informa `sources/status` las fuentes de listas. Ya casi está resuelto:
  el catálogo de fuentes de Tusdatos (`/api/fuentes-colombia`, consultado en el sandbox el
  13-11-2026) trae los 12 códigos que usa el sistema, escritos igual (`ofac`, `lista_onu`,
  `peps`, `peps_funcion_publica`, `procuraduria`…). Las cuatro fuentes que hoy informa
  `sources/status` en el sandbox también salen de ese catálogo. Falta verlo con
  credenciales reales: el trabajador avisa si alguna no aparece.
- Si `/api/retry` tiene un límite de veces por reporte, un tiempo mínimo entre uno y otro
  o deja de servir pasado un tiempo. La documentación no pone ninguno, pero tampoco dice
  que no existan, y documenta un 400 sin explicar cuándo sale. Por eso el sistema se pone
  su propio límite (tres recargas en 24 horas) y deja de insistir si Tusdatos responde
  con error.
- Cómo funcionan los «auto reintentos» del plan. La propuesta comercial los nombra, y el
  webhook `individualRetry` avisa «cuando un proceso de retry encuentra nuevos hallazgos
  relevantes». Pero la documentación no dice quién lanza ese retry, cada cuánto, ni si el
  reporte se actualiza. Lo más probable es que sea un proceso suyo; falta que lo confirmen.
  Para aprovecharlo habría que recibir el webhook, lo que exige un endpoint público
  nuestro; queda para después. Mientras tanto, nuestra recarga diferida cubre el caso.
- El «lanzamiento de fuente puntual» que nombra la nota de `sources/status`. No hay
  ninguna ruta documentada para eso.
- Cuánto tiempo guarda Tusdatos los reportes y PDF, y si se puede pedir que los borren.
- Si firman un contrato de transmisión de datos personales. La propuesta solo pide nuestra
  política de tratamiento.

## Pendiente

- La búsqueda en el historial no se puede probar en el sandbox, porque allí no existe.
  Hay que confirmarla con credenciales reales (ver «No documentado» arriba).
- Tusdatos no publica con qué códigos informa el estado de OFAC, ONU, PEP y las demás
  listas. El sistema deja registrado cuáles faltan en la primera consulta real.
- Con credenciales reales falta verificar: el PDF, el reintento de fuentes fallidas (en
  especial horas después del cierre, que es lo que usa la recarga automática), la
  forma real de cada fuente, la regla de PEP por función pública y el aviso de documento
  no validado.
- Falta la alarma de CloudWatch sobre la métrica de créditos, para que el aviso le llegue
  a alguien y no se quede solo en los registros.
- Para activarlo en staging, ver [operación, «En AWS»](OPERACION_PRUEBAS_Y_PENDIENTES.md#en-aws).
