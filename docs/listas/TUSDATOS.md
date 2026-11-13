  # Consultas de listas con Tusdatos

  Esta guía explica cómo funciona la consulta de listas cuando el módulo trabaja con
  Tusdatos (la modalidad «externa»). Está pensada para quien revisa los resultados o
  atiende la operación. El detalle técnico está en la
  [arquitectura, sección 11](ARQUITECTURA_LISTAS.md#11-cómo-se-añade-una-fuente-o-un-proveedor).

  Revisada contra el código el 13-11-2026.

  ## Qué se consulta

  Tusdatos busca por **número de documento**. Se aceptan cuatro tipos:

  | Documento | Qué hace falta |
  |---|---|
  | Cédula de ciudadanía (CC) | Solo el número |
  | Cédula de extranjería (CE) | El número y la fecha de expedición |
  | Pasaporte | El número y el nombre completo |
  | NIT | Solo el número, sin dígito de verificación (si se escribe «900.123.456-7», el sistema quita el «-7») |

  Si falta algo, el portal rechaza la consulta antes de enviarla y no se gasta ningún
  crédito. El nombre que se escribe en el formulario solo se envía con el pasaporte; en
  los demás casos Tusdatos resuelve el nombre por su cuenta.

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

  Cada fuente queda en uno de estos estados:

  - **Consultada:** Tusdatos la revisó. Si encontró algo, aparece como candidato.
  - **Fallida:** Tusdatos no pudo consultarla. Se intenta una vez más, sin costo; si
    sigue fallando, la consulta no puede concluir. Si Tusdatos dice que la fuente está
    caída, el sistema espera a que vuelva antes de intentarlo. Si no vuelve a tiempo, la
    fuente queda fallida con el motivo «caída o en mantenimiento».
  - **No disponible:** la fuente no vino en el reporte, por ejemplo porque no está en el
    plan contratado.

  Con eso, la consulta termina así:

  - **Completada, sin candidatos:** todas las fuentes obligatorias se revisaron y no hubo
    registros.
  - **Completada, con candidatos:** hay registros para revisar. Un candidato es una
    alerta, no una decisión: alguien tiene que confirmar si se trata de la misma persona.
  - **Parcial o no concluyente:** faltó alguna fuente obligatoria o pasó algo que impide
    afirmar que no hay registros. Hay que repetir la consulta o revisarla a mano.

  Tres casos especiales:

  - **PEP por función pública** solo viene en el reporte cuando hay un registro. Por eso,
    si no aparece, no impide concluir. Si aparece con error, sí lo impide. Esta regla se
    confirmará cuando haya credenciales reales.
  - **Documento no validado:** a veces Tusdatos avisa que no pudo validar el documento
    contra la fuente oficial (por ejemplo, la cédula no coincide con la Registraduría). El
    portal lo muestra en rojo. Un «sin candidatos» con este aviso no es confiable:
    conviene revisar el número y el tipo de documento antes de darlo por bueno.

  - **Documento no encontrado:** si el NIT no está en el registro mercantil, o la cédula
    de extranjería no está en Migración Colombia, Tusdatos lo dice de una vez. La consulta
    se cierra con ese mensaje para que se revise el número antes de repetirla.
  - **Documento no vigente:** si la empresa no está activa en la cámara de comercio, o la
    cédula de extranjería no está vigente, las listas se consultan igual y el resultado
    lleva un aviso en rojo. Se consulta igual porque una empresa cancelada o una cédula
    vencida puede seguir apareciendo en una lista.

  ## Verificación del NIT y de la cédula de extranjería

  Antes de consultar listas de un NIT o de una cédula de extranjería, el sistema le pide a
  Tusdatos que confirme que el documento existe:

  - **NIT:** lo busca en las cámaras de comercio (RUES) y devuelve si la empresa está activa.
  - **Cédula de extranjería:** la busca en Migración Colombia, con la fecha de expedición,
    y devuelve si está vigente.

  Con eso pasa una de tres cosas:

  - **No existe:** la consulta se cierra sin consultar listas, con el mensaje «Tusdatos no
    encontró el NIT…» o «…la cédula de extranjería…».
  - **Existe pero no está vigente o activa:** se consultan las listas y el resultado lleva
    el aviso «Documento no vigente».
  - **Existe y está vigente:** se consultan las listas normalmente.

  Si la verificación falla (Tusdatos no responde o contesta algo que no se entiende), la
  consulta sigue sin ella. Se hace una sola vez por consulta y nunca se repite sola.

  Solo se guarda el resultado (por ejemplo «ACTIVA» o «Nit no encontrado»). No se guardan
  la razón social, el nombre, la nacionalidad ni las fechas que devuelve Tusdatos.

  **Ojo con el costo:** la documentación de Tusdatos no dice si estas verificaciones gastan
  crédito. Si cobran, cada NIT o cédula de extranjería costaría dos consultas en vez de una.
  Para apagarlas, poner `LISTAS_TUSDATOS_VERIFICAR_DOCUMENTO=false`. Las cédulas de
  ciudadanía y los pasaportes no se verifican.

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

  ## Tiempos

  Una consulta tarda en promedio un minuto. Si en 15 minutos Tusdatos no responde, la
  consulta se cierra como no concluyente. Entre una consulta y la siguiente el sistema
  espera 5 segundos, como pide Tusdatos.

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

  **No documentado (hay que preguntarlo)**

  - Si se cobra cuando el documento no existe (400), cuando el titular no autoriza (403) o
    cuando todas las fuentes fallan. La frase general dice que toda consulta gasta crédito,
    pero no aclara estos casos.
  - Si se cobra al repetir dentro de 6 horas una cédula de extranjería, un pasaporte o un
    NIT. La regla de las 6 horas solo se menciona para la cédula de ciudadanía.
  - Si las validaciones `verify/nit` y `verify/ce` cobran y si vienen incluidas en el plan
    (la propuesta nombra «Información estado documento de identidad»). Solo la de PPT dice
    que cobra. El sistema ya las usa: ver «Verificación del NIT y de la cédula de
    extranjería».
  - Si la consulta servida desde la caché de 6 horas aparece en el historial
    (`/api/v1/checks`), si `check_id` es el mismo id que recibe `report_json` y en qué formato
    viene `created_at`. El esquema solo dice que son textos.
  - Cómo se envían `country` y `document_type` al historial. La documentación los marca como
    parámetros de ruta, pero la ruta escrita los pone después del `?`. El sistema los envía
    como `?country=CO&document_type=CC`. En el sandbox las dos formas responden 404, porque
    allí el historial no existe.
  - Con qué códigos informa `sources/status` las fuentes de listas. La sección de evidencias
    usa `ofac`, `ofac_nombre`, `lista_onu`/`onu`, `interpol`, `europol` y `cidob`, que son
    los mismos códigos que usa el sistema. Pero esos son nombres de archivo de las capturas, y
    la misma sección muestra casos en que no coinciden con el reporte (`personeria_bogota` y
    `personeriabog`). Sirve como pista, no como confirmación. Listas y PEP no aparece ahí.
  - Si hay un límite de reintentos por reporte o un tiempo mínimo entre uno y otro.
  - Cómo se relacionan los «auto reintentos» del plan con nuestro reintento: si Tusdatos ya
    reintenta solo, el nuestro podría sobrar.
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
  - Con credenciales reales falta verificar: el PDF, el reintento de fuentes fallidas, la
    forma real de cada fuente, la regla de PEP por función pública y el aviso de documento
    no validado.
  - Falta la alarma de CloudWatch sobre la métrica de créditos, para que el aviso le llegue
    a alguien y no se quede solo en los registros.
  - Para activarlo en staging, ver
    [operación, «Antes de cualquier ambiente compartido»](OPERACION_PRUEBAS_Y_PENDIENTES.md#antes-de-cualquier-ambiente-compartido-staging).
