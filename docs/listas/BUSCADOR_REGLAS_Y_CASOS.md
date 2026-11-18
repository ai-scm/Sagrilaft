# Buscador por archivos: reglas de clasificación y casos de aceptación

Estado verificado contra el código el 2026-11-12. Reglas funcionales aprobadas
como **AF-F6-01** (2026-11-08). Implementación: `services/listas/motor_busqueda.py`
(reglas `clasificacion-f63-v1`, algoritmo `recuperacion-f63-v1`, catálogo
`motor-f63-v1`) y los comparadores de `domain/listas/comparacion_*.py`.

Documentos relacionados: [arquitectura](ARQUITECTURA_LISTAS.md) (contrato 2.1,
flujo de la consulta, persistencia) y [operación y pruebas](OPERACION_PRUEBAS_Y_PENDIENTES.md)
(cómo ejecutar los casos de este documento).

Estas reglas aplican solo a la modalidad **archivos**. El simulador (contrato 2.0)
no produce ALTA/MEDIA/BAJA y el portal lo indica así.

---

## 1. Alcance

- Sujetos: empresas y personas naturales, sean clientes o proveedoras, y el
  representante legal cuando corresponda, siempre como consultas separadas.
- Cliente o proveedor es un rol comercial: **no cambia el nivel**.
- La naturaleza (persona o empresa) sale del expediente. Tener NIT no convierte a una
  persona en empresa. Una persona natural no necesita representante para ser consultada.
- Fuera de alcance: buques, aeronaves, beneficiarios finales, socios, búsqueda sin
  expediente y revisión automática de relacionados. Los registros de transporte de
  OFAC se conservan, pero se excluyen de la búsqueda.

## 2. De dónde salen los datos consultados

`services/listas/preparacion_criterios.py` prepara los criterios a partir de una copia
del expediente guardado (consulta de contraparte y representante).
`servicio_archivos_portal.py` hace lo mismo para la consulta individual con los datos
editados en pantalla.

| Dato del expediente | Cómo se usa |
|---|---|
| `tipo_persona` natural | Contraparte PERSONA, aunque tenga NIT. Su bloque personal (paso 3 del formulario, «Representante legal o persona natural») le pertenece; no se duplica como representante |
| `tipo_persona` jurídica | Contraparte ENTIDAD, con `razon_social` como nombre; el representante va en una consulta PERSONA aparte si tiene datos utilizables |
| Naturaleza ausente o no reconocida | NO_DETERMINADO; no se deduce por el documento |
| `numero_identificacion`, `digito_verificacion` | Identificador; el dígito se transporta separado solo cuando el esquema lo admite; nunca se calcula ni se recorta del número |
| `PAS` | Alias de tipo para PASAPORTE |
| `fecha_nacimiento` / `fecha_expedicion` | Campos distintos; nunca se usa uno por otro |
| `nacionalidad` | Mediante un catálogo explícito; no se infiere ciudadanía |
| `ciudad_nacimiento`, `ciudad_expedicion`, domicilio, residencia, funciones | Ubicaciones con su rol; no se extrae un país de un texto |
| `pais`, `pais_funciones` | Solo para su rol geográfico; **nunca** como país emisor de un documento |
| `tipo_contraparte` | Procedencia cliente/proveedor; no afecta los criterios |

La **consulta individual** acepta nombre, tipo de documento (CC, NIT o PASAPORTE en el
formulario), número, país del documento (ISO de dos letras) y fecha de nacimiento.
Sin país del documento, un documento no puede confirmar jurisdicción ni llegar a ALTA.
El servidor no completa por su cuenta un nombre editado con datos guardados.

Un dato no interpretable (fecha, país o tipo desconocido) se conserva con una
advertencia y no cuenta como criterio aplicado. Si era un criterio exigido, la
consulta termina NO_CONCLUYENTE.

## 3. Qué es un dato fuerte

**Identificador fuerte:** valor completo comparable, tipo y esquema conocidos,
jurisdicción compatible cuando el esquema la exige, control fiscal completo cuando
aplica, calidad **CONFIRMADO** y sin asignación a varios registros de la misma fuente.
Si la evaluación se truncó, no se puede afirmar esa falta de ambigüedad.

**Fecha de nacimiento fuerte:** completa, precisa, no aproximada, en calendario
gregoriano, CONFIRMADA y de la misma identidad dentro del registro. Un año, un mes, un
rango o un dato reportado solo aportan compatibilidad.

**Calidad:** la fuente puede declarar CONFIRMADO, REPORTADO, DESCONOCIDO o FALSO.
Desconocido, reportado o sin calidad nunca se convierten en confirmado; FALSO nunca
corrobora. En OFAC, `ValidityID` no equivale a fiabilidad, y la autoridad general de la
lista no confirma cada atributo.

## 4. Niveles

| Nivel | Persona natural o representante | Empresa |
|---|---|---|
| **ALTA** | Documento fuerte exacto; o nombre completo sólido más nacimiento fuerte de la misma identidad. En ambos casos sin contradicción fuerte | NIT o registro empresarial fuerte exacto en su esquema y jurisdicción, sin contradicción fuerte |
| **MEDIA** | Nombre completo o alias no débil coincidente; variante menor de un nombre completo; documento igual al que le falta contexto o calidad | Razón social o nombre comercial no débil coincidente; variante societaria explicada; identificador igual con calidad o contexto incompletos |
| **BAJA** | Nombre parcial utilizable, alias débil o documento cuestionado sin otra base; coincidencia nominal con contradicción fuerte | Nombre parcial o ampliado, alias débil; coincidencia nominal con datos fiscales fuertes contradictorios |

- Solo el nombre nunca da ALTA. Para una empresa, nombre más domicilio, dominio o país
  tampoco: la ALTA empresarial exige el identificador fiscal o registral fuerte.
- Cada candidato tiene exactamente un nivel. No hay cuarta categoría.
- Sin candidatos, la consulta informa ausencia **dentro de la cobertura consultada**, sin
  nivel. Una consulta fallida o incompleta es NO_CONCLUYENTE, aunque conserve
  candidatos parciales.
- La ausencia de un dato opcional no rebaja una ALTA ya sustentada. La ausencia de un
  componente necesario del propio identificador (por ejemplo, su jurisdicción) sí impide
  la ALTA por esa vía.

## 5. Orden con contradicciones

El motor aplica esta precedencia:

| Situación | Resultado |
|---|---|
| Identificador fuerte exacto y contradicción fuerte (nacimiento distinto, nombre incompatible con todos los nombres sólidos) | **MEDIA con revisión prioritaria** (prevalece sobre la fila siguiente) |
| Misma base fiscal con dígitos de verificación explícitos distintos | MEDIA con conflicto fiscal prioritario. Un dato marcado falso no sustenta ese conflicto |
| Coincidencia nominal con nacimiento fuerte incompatible, o con un identificador único vigente incompatible | **BAJA con contradicción** destacada |
| Identificador fuerte, naturaleza compatible, sin contradicción fuerte | ALTA |
| Persona con nombre completo sólido y nacimiento fuerte de la misma identidad | ALTA |
| Nombre o alias sólido completo, o documento utilizable sin corroboración | MEDIA |
| Nombre parcial, alias débil o documento cuestionado sin otra base | BAJA |

- Un pasaporte distinto no prueba exclusión: una persona puede tener varios. Un
  identificador único distinto solo es contradicción fuerte si ambos están bien
  identificados y hay una **vigencia confirmada** que incluya la fecha de referencia de
  la consulta. Sin ella se muestra la diferencia sin declarar contradicción fuerte.
- Nacionalidad, ciudadanía, residencia o domicilio distintos se muestran como diferencias
  de contexto. No excluyen ni elevan por sí solos.
- Un dato ausente no es contradicción.
- El nivel y la prioridad de revisión son cosas distintas. La lista ordena primero las
  contradicciones prioritarias.

## 6. Comparación por tipo de dato

**Nombres**

- Se normalizan mayúsculas, espacios, puntuación y tildes. Ñ y N se tratan como
  variación, no como igualdad literal. Se conserva el original.
- Cambiar el orden de las partes no impide la coincidencia. Cada nombre documentado se
  evalúa completo y por separado; nunca se combinan fragmentos de alias distintos.
- Se recupera una sustitución, inserción, omisión o transposición adyacente en una
  palabra de al menos cuatro caracteres. Para considerarlo nombre completo admite como
  máximo una palabra modificada. Las palabras numéricas no se comparan aproximadamente.
- En empresas se reconoce S.A./S.A.S. al final como variante explicada. «Trading»,
  «Filial» y otros términos distintivos sí cuentan.
- Los apodos y alias marcados débiles se conservan como tales.
- Entrada genérica sin otro criterio (lista técnica versionada: «juan», «maria», «jose»,
  «empresa», «comercial», «servicios», «cliente», «proveedor») pide más datos antes de
  admitir la búsqueda.
- **No hay transliteración generada.** Las transliteraciones publicadas por la fuente
  se comparan como nombres independientes.

**Identificadores**

- Igualdad del valor completo según tipo y esquema; sin aproximación numérica. Ceros,
  letras y mayúsculas se conservan.
- `nit-co-v1` (solo NIT de CO) separa puntos de agrupación y un dígito explícito tras
  guion. Si el dígito separado contradice al incluido, el criterio no es utilizable.
  `registro-separador-v1` permite espacios o guiones solo donde el catálogo lo declara.
- Máscaras, marcadores de ausencia y valores sin letras ni números no son utilizables.
- Un mismo número en fuentes distintas no fusiona sujetos.

**Fechas y relaciones**

- Se revisan todas las alternativas publicadas: una compatible evita declarar
  incompatibilidad global por las demás.
- Un registro con varias identidades y sin referencia de identidad no se vincula con
  seguridad.
- Las relaciones publicadas son contexto: no confirman identidad ni trasladan una
  coincidencia o sanción al relacionado. No hay búsqueda recursiva.

## 7. Qué ve el analista y qué queda como evidencia

Implementado en `ResultadoConsultaListas.jsx` y en `services/listas/presentacion_informe.py`
(informe `informe-listas-f6-v2`):

- Nivel, explicación de la regla, revisión prioritaria y comparación por dato: coincide,
  compatible, diferente, ausente o no aplicado, con calidad y referencia de origen.
- Nombres, alias, documentos, fechas, ubicaciones, observaciones y relaciones de la
  generación consultada.
- Fuente, versión, generación y trazabilidad (reglas, algoritmo, hashes), tomadas del
  manifiesto admitido y no de la versión activa del momento.
- Evidencias con estado, generador y SHA-256. El PDF incluye los hashes del resultado y
  del manifiesto, y no el suyo propio. Todos los textos de la fuente se escapan antes de
  construir el HTML del PDF.
- **Sin porcentajes ni puntajes** en pantalla, respuestas ni PDF. Los cálculos internos
  solo sirven para recuperar candidatos y no deciden el nivel.
- Distingue completa con candidatos, completa sin candidatos, parcial y fallida.
- La revisión humana se guarda aparte. No reescribe el informe ni reclasifica consultas
  antiguas.

Cada consulta conserva: identificador, actor, expediente y rol, criterios originales y
efectivos, cobertura fijada por fuente y versión con hashes, política, reglas,
algoritmo, catálogo, parámetros, resultado, advertencias, criterios no aplicados e
informe con hash.

Límites internos del motor (`ParametrosMotor`): 50.000 registros evaluados, 1.000
candidatos y 40 partes de nombre. Superarlos produce PARCIAL/NO_CONCLUYENTE, con las
advertencias `LIMITE_REGISTROS_NO_CONCLUYENTE`, `LIMITE_CANDIDATOS_NO_CONCLUYENTE` o
`NOMBRE_FUENTE_SUPERA_LIMITE`. Nunca se recorta en silencio.

## 8. Datos de referencia de los casos

Ficticios, salvo los R, que están observados en la publicación OFAC del 2026-11-06
(XML SHA-256 `60698e6e…805f`).

| Registro | Datos |
|---|---|
| S1, persona | Juan Carlos Pérez Gómez; alias sólido Juan Pérez; alias débil El Capitán; pasaporte AB0001234 CO confirmado; nacimiento 1980-03-15 confirmado; nacionalidad y ciudadanía CO; nacido en Medellín; residencia Bogotá |
| S2, empresa | Comercial Andina S.A.S.; alias Andina Comercial; registro REG-00042 CO confirmado; domicilio Bogotá; constitución 2001-04-20. Variante S2-NIT: NIT 900123456, dígito 8, CO, confirmado |
| S3, homónimo | Mismo nombre que S1; pasaporte CD0007777 CO; nacimiento 1989-07-21 confirmado |
| S4, relacionado | Otro Sujeto de Prueba, con relación hacia S1 |
| S5, lista propia | Identificador AbC001 sensible a mayúsculas, sin jurisdicción |
| R1 | OFAC UID 22790, persona; «MADURO MOROS Nicolas/Nicolás»; nacimiento 1962-11-23 con fiabilidad Unknown |
| R2 | OFAC UID 17022, entidad; Open Joint-Stock Company Rosneft Oil Company; alias OJSC Rosneft Oil Company, Rosneft y otros |
| R3 | OFAC UID 27304, buque Adrian Darya 1; alias Grace 1 (F.K.A.); IMO 9116412; bandera Iran (Confirmed) |

## 9. Matriz de casos

Estado de cada caso:

- **26P**: uno de los 26 prioritarios, con prueba integrada (HTTP, trabajador, historial
  y PDF) en F6.6 y, para los 21 de clasificación, también prueba del motor.
- **Oficial**: comprobado con la copia oficial completa en F6.6.
- **Esperado**: resultado definido en el diseño; sin prueba de aceptación dedicada
  (algunas pruebas del motor lo cubren en parte).
- **Fuera de alcance** o **No implementado**: no se puede cumplir hoy.

### Anclas reales

| Caso | Entrada | Esperado | Estado |
|---|---|---|---|
| R-01 | PERSONA, Nicolás Maduro Moros | Incluye UID 22790 en MEDIA | Oficial (3 candidatos) |
| R-02 | R-01 + nacimiento 1962-11-23 | UID 22790 sigue MEDIA (fiabilidad Unknown) | Oficial |
| R-03 | ENTIDAD, OJSC Rosneft Oil Company | UID 17022 en MEDIA | Oficial (1 candidato) |
| R-04 | ENTIDAD, Rosneft | UID 17022 en MEDIA; puede haber otros | Oficial (159 candidatos) |
| R-05 a R-08 | Buque por nombre, IMO o bandera; persona con nombre de buque | Definidos en el diseño | Fuera de alcance |

### Nombres

| Caso | Entrada sobre | Esperado | Estado |
|---|---|---|---|
| N-01 | S1: JUAN CARLOS PEREZ GOMEZ | MEDIA | 26P |
| N-02 | S1: Pérez Gómez, Juan Carlos | MEDIA | Esperado |
| N-03 | S1: Juan Pérez (alias sólido) | MEDIA | 26P |
| N-04 | S1: El Capitán (alias débil) | BAJA | 26P |
| N-05 | S1: Juan Carlos Peres Gómez | MEDIA | 26P |
| N-06 | S1: uJan Carlos Pérez Gómez | MEDIA | 26P |
| N-07 | S1: Juan Carlos Pérez (falta apellido) | BAJA | Esperado |
| N-08 | S1: Juan | Pide más datos; no admite | Esperado |
| N-09 | S1: principal y alias en la misma solicitud | Un candidato con varios motivos, MEDIA | Esperado |
| N-10 | S1: fragmentos de alias distintos | Sin igualdad artificial | Esperado |
| N-11 | Variante S1 en otro alfabeto, entrada igual | MEDIA | Esperado |
| N-12 | Variante S1 por transliteración generada | MEDIA, nunca ALTA por eso | No implementado (no hay transliteración) |
| N-13 | S2: Comercial Andina SA | MEDIA con diferencia societaria explicada | Esperado |

### Identificadores

| Caso | Entrada sobre | Esperado | Estado |
|---|---|---|---|
| I-01 | S1: pasaporte AB0001234 CO | ALTA | 26P |
| I-02 | S1: AB0001235 CO, sin nombre | Sin candidatos | 26P |
| I-03 | S1: AB0001234 sin país | MEDIA | 26P |
| I-04 | S1: AB0001234 país distinto | MEDIA con discrepancia | Esperado |
| I-05 | S1: cédula AB0001234 | Sin candidato por documento | Esperado |
| I-06 | S1: AB1234 (sin ceros) | Sin candidato por documento | 26P |
| I-07 | S2: REG 00042 CO | ALTA, conservando el original | Esperado |
| I-08 | Variante S1 con pasaporte marcado falso | BAJA, nunca ALTA | Esperado |
| I-09 | Mismo pasaporte confirmado en dos sujetos | Ambos MEDIA con ambigüedad | Esperado |
| I-10 | S1: nombre exacto y pasaporte distinto | MEDIA con discrepancia | Esperado |
| I-11 | S5: AbC001 / abc001 | MEDIA / sin candidato | Esperado (no hay lista propia cargada) |
| I-12 | Tipo de identificador desconocido exigido | Rechazo o NO_CONCLUYENTE | Esperado |

### Corroboración y contradicciones

| Caso | Entrada sobre | Esperado | Estado |
|---|---|---|---|
| C-01 | S1: nombre + 1980-03-15 | ALTA | 26P |
| C-02 | S1: nombre + nacimiento confirmado distinto | BAJA prioritaria | 26P |
| C-03 | S1: pasaporte exacto + nacimiento distinto | MEDIA prioritaria | 26P |
| C-04 | Variante S1 solo año 1980 | MEDIA | 26P |
| C-05 | Variante S1 con rango 1979–1981 | MEDIA | Esperado |
| C-06 | Variante S1 con fechas alternativas | ALTA si una alternativa es fuerte; si no, MEDIA | Esperado |
| C-07 | S1: nombre + nacionalidad CO | MEDIA | Esperado |
| C-08 | S1: nombre + nacionalidad distinta o ausente | MEDIA, diferencia etiquetada | Esperado |
| C-09 | S1: nombre + lugar de nacimiento | MEDIA | Esperado |
| C-10 | S1: nombre + domicilio igual o distinto | MEDIA | Esperado |
| C-11 | Solo dirección, fecha o programa | Pide criterio primario | Esperado |
| C-12 | S1 y S3, mismo nombre | Dos candidatos MEDIA | 26P |
| C-13 | S1 y S3 + nacimiento de S1 | S1 ALTA, S3 BAJA con contradicción | Esperado |
| C-14 | S4 relacionado con S1 | S1 directo; S4 solo en contexto | Esperado |
| C-15 | Datos reportados o desconocidos coincidentes | No elevan el nivel | 26P |
| C-16 | Mismo país en varios roles | No suma corroboraciones | Esperado |
| C-17 | S2 + fecha de constitución | No se trata como nacimiento | Esperado |
| C-18 | Dirección histórica coincidente | Contexto, no ALTA | Esperado |
| C-19 | Nombre y fecha de identidades distintas | MEDIA; no se combinan | 26P |

### Empresas

| Caso | Entrada | Esperado | Estado |
|---|---|---|---|
| B-01 | NIT base, dígito y jurisdicción iguales | ALTA | 26P |
| B-02 | Fuente 900.123.456-8; entrada separada | ALTA solo si el esquema lo determina sin ambigüedad | Esperado |
| B-03 | Comercial Andina frente a Comercial Andina Trading | BAJA, registros separados | 26P |
| B-04 | Razón social y domicilio iguales, sin registro | MEDIA | Esperado |
| B-05 | NIT igual sin jurisdicción | MEDIA | Esperado |
| B-06 | Mismo nombre y dominio, NIT únicos incompatibles con vigencia | BAJA prioritaria | 26P |
| B-07 | Misma base, dígitos explícitos distintos | MEDIA prioritaria | 26P |
| B-08 | Mismos datos como cliente y como proveedor | Mismos niveles, sin mezclar empresa y representante | 26P |

### Cobertura y operación

| Caso | Condición | Esperado | Estado |
|---|---|---|---|
| O-01 | Fuente disponible, sin candidato | COMPLETADA / SIN_CANDIDATOS (no es certificado de no inclusión) | Esperado |
| O-02 | Fuente requerida sin versión activa o trabajador fallido | NO_CONCLUYENTE | 26P (FALLIDA) |
| O-03 | Se activa otra versión con una consulta pendiente | Termina con la versión admitida | 26P |
| O-04 | Se restaura una versión después de consultar | Conserva resultado y bytes del PDF | 26P |
| O-05 | Evidencia corrupta o versión bloqueada durante la ejecución | NO_CONCLUYENTE, sin sustituir versión | Esperado (cubierto por pruebas F6.4) |
| O-06 | Candidatos sobre el límite | PARCIAL / NO_CONCLUYENTE | Esperado (cubierto por pruebas F6.4) |
| O-07 | Lista propia y OFAC con coincidencias | Registros separados por fuente | No implementado (no hay lista propia) |
| O-08 | Proveedor que solo devuelve un puntaje | Sin candidato clasificado; limitación de cobertura | No implementado (no hay adaptador externo) |
| O-09 | Criterio opcional o exigido no soportado | Advertencia / NO_CONCLUYENTE | Esperado |
| O-10 | Reintento con la misma clave / nueva consulta | Misma operación / cobertura propia | Esperado (idempotencia probada) |
| O-11 | Usuario sin permisos | 403/404 sin fuga de datos | 26P |
| O-12 | Resultado ALTA y revisión humana | El expediente no cambia | 26P |

Los 26 prioritarios se ejecutan con `tests/persistencia_listas/test_aceptacion_f66.py`.
Pasar estos casos no prueba la ausencia de falsos positivos o negativos en general.

## 10. Pendiente antes de usar las reglas con datos reales

- **Con OFAC real, hoy no hay ALTA por documento.** El lector OFAC asigna a los documentos
  calidad DESCONOCIDO, o FALSO si están marcados como fraudulentos, nunca CONFIRMADO
  ([arquitectura, adaptador OFAC](ARQUITECTURA_LISTAS.md#adaptador-ofac-advanced)). Un
  documento OFAC coincidente queda como máximo en MEDIA. La ALTA por nombre y nacimiento
  solo es posible si la fecha publicada tiene fiabilidad Confirmed. Cambiarlo exigiría un
  mapa de confianza aprobado por campo y fuente, no un ajuste del motor.
- Corpus representativo etiquetado y objetivos de recuperación, falsos positivos y carga
  de revisión acordados con cumplimiento. La calibración actual son 20 pares nominales
  ficticios (14 recuperaciones esperadas, 6 negativos, sin ALTA solo por nombre).
  Método acordado en el diseño:
  1. Revisar con el responsable funcional los niveles y ejemplos de este documento.
  2. Resolver la semántica de fechas, calidad y tipos contra el XSD y las notas oficiales.
  3. Preparar un corpus etiquetado con positivos, alias, homónimos, negativos, datos
     ausentes y contradictorios, registrando quién etiquetó y qué se afirma.
  4. Separar el corpus de ajuste del de validación final. R-01–R-04 son anclas de
     recuperación, no un corpus representativo.
  5. Medir por separado tres cosas: si se recuperó el candidato esperado, si la
     explicación es correcta y si el nivel es el debido. Un candidato perdido en la
     recuperación no se corrige cambiando la clasificación. Un MEDIA por calidad
     incompleta no es un falso negativo: el candidato sigue presente.
  6. Medir también el volumen de alertas y las diferencias por tipo de sujeto, idioma,
     alias, longitud y datos disponibles. Las BAJA siguen visibles; no se ocultan para
     aparentar menos alertas.
  7. Acordar los objetivos con cumplimiento y su viabilidad con el líder técnico. Los
     parámetros internos nunca se muestran como porcentajes ni definen niveles.
- Política de qué identificadores completos ve cada rol y cómo se enmascaran en listados
  (**propuesto**: enmascarados en listados y completos solo en el detalle con permiso de
  evidencia; no aprobado).
- Mapeo de la vigencia documental OFAC: el adaptador no la rellena; hoy ninguna diferencia
  de identificadores únicos OFAC llega a contradicción fuerte por vigencia.
- Catálogos OFAC de tipos documentales y calidades: no están homologados de forma
  exhaustiva. Lo no mapeado se trata como no interpretado.
- Captura de fechas parciales en la consulta: el contrato admite solo una fecha completa.
  Un año de entrada nunca se convierte en 1 de enero.
