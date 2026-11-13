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
  | NIT | Solo el número |

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
    sigue fallando, la consulta no puede concluir.
  - **No disponible:** la fuente no vino en el reporte, por ejemplo porque no está en el
    plan contratado.

  Con eso, la consulta termina así:

  - **Completada, sin candidatos:** todas las fuentes obligatorias se revisaron y no hubo
    registros.
  - **Completada, con candidatos:** hay registros para revisar. Un candidato es una
    alerta, no una decisión: alguien tiene que confirmar si se trata de la misma persona.
  - **Parcial o no concluyente:** faltó alguna fuente obligatoria o pasó algo que impide
    afirmar que no hay registros. Hay que repetir la consulta o revisarla a mano.

  Dos casos especiales:

  - **PEP por función pública** solo viene en el reporte cuando hay un registro. Por eso,
    si no aparece, no impide concluir. Si aparece con error, sí lo impide. Esta regla se
    confirmará cuando haya credenciales reales.
  - **Documento no validado:** a veces Tusdatos avisa que no pudo validar el documento
    contra la fuente oficial (por ejemplo, la cédula no coincide con la Registraduría). El
    portal lo muestra en rojo. Un «sin candidatos» con este aviso no es confiable:
    conviene revisar el número y el tipo de documento antes de darlo por bueno.

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

  ## Pendiente

  - Tusdatos no ha respondido cómo recuperar el reporte de una cédula que ya estaba en
    su caché (responde sin número de trabajo). Mientras tanto, esas consultas se cierran
    con un aviso que sugiere «Forzar actualización».
  - Con credenciales reales falta verificar: el PDF, el reintento de fuentes fallidas, la
    forma real de cada fuente, la regla de PEP por función pública y el aviso de documento
    no validado.
  - Para activarlo en staging, ver
    [operación, «Antes de cualquier ambiente compartido»](OPERACION_PRUEBAS_Y_PENDIENTES.md#antes-de-cualquier-ambiente-compartido-staging).
