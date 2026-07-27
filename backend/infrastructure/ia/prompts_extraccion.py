from typing import Dict

# ═══════════════════════════════════════════════════════════════
# Prompts de extracción por tipo de documento
# ═══════════════════════════════════════════════════════════════

PROMPTS_EXTRACCION: Dict[str, str] = {
    "cedula_representante": """Analiza este documento de identidad (puede ser de cualquier país) y extrae exactamente los siguientes campos, adaptándote a la terminología local del formato:
- tipo_documento: tipo de documento tal como aparece en el encabezado. Normaliza a un formato genérico si es posible (ej: "CEDULA DE CIUDADANIA", "CEDULA DE EXTRANJERIA", "PASAPORTE").
- nombre: nombre completo de la persona (nombres y apellidos)
- numero_documento: número del documento (solo caracteres alfanuméricos o digitos, sin puntos ni espacios)
- fecha_expedicion: fecha de expedición en formato YYYY-MM-DD
- lugar_expedicion: ciudad, municipio o país de expedición
- fecha_nacimiento: fecha de nacimiento en formato YYYY-MM-DD. Ejemplo: "1990-08-15".
- lugar_nacimiento: ciudad o municipio de nacimiento tal como aparece en el documento

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "rut": """Analiza este documento de registro tributario o fiscal (como RUT, RUC, RFC, CUIT, etc., dependiendo del país) y extrae la información solicitada. Adapta tu búsqueda a la estructura y nombres de secciones equivalentes en el documento proporcionado:
- razon_social: nombre o razón social completa
- nit: número de identificación tributaria o fiscal (solo alfanuméricos o digitos, sin puntos ni guiones) ¡ATENCION A BARRERAS VISUALES!
- actividades_economicas: lista de códigos de actividad económica con su descripción (array de strings)
- codigo_ica: código de la actividad principal a nivel local/municipal (si aplica). Devuelve solo el número, sin texto adicional.
- tipo_persona: tipo de persona o contribuyente (ej. Jurídica, Natural). Normaliza el valor extraído a "Persona Jurídica" o "Persona Natural" según corresponda.
- nombre_representante: nombre completo del representante legal. Busca en la sección de representación o apoderados y concatena los nombres y apellidos -> Primer Nombre, Segundo Nombre o Otros Nombres, Primer Apellido, Segundo Apellido. Devuelve una sola cadena.
- fecha_documento: fecha de generación, inscripción o actualización del documento en formato YYYY-MM-DD
- direccion: dirección registrada
- correo: correo electrónico registrado
- telefono: número de teléfono registrado (solo dígitos, sin espacios ni guiones)
- cedula_representante: número de identificación del representante legal. Búscalo en la sección "Representación" → campo Número de identificación". REGLAS ESTRICTAS: (1) El campo "100. Tipo de documento" contiene SOLO un código corto de 2 dígitos (13=CC, 22=CE, 31=NIT, 41=PAS) — ese código NUNCA forma parte del número de identificación. (2) Lee el número que aparece EXCLUSIVAMENTE después del label "101." — ignorando completamente la fila del "100.". (3) Si el valor que extrajiste empieza por 13, 22, 31 o 41 seguido de más dígitos, esos 2 primeros dígitos son el código del tipo de documento que se coló accidentalmente — descártalos y devuelve solo los dígitos restantes. (4) Devuelve únicamente dígitos, sin espacios ni guiones. Si no encuentras el campo 101, devuelve null.
- clasificacion_dv: dígito de verificación del NIT. Búscalo en la sección "IDENTIFICACIÓN" → campo "6. DV". Devuelve ÚNICAMENTE el dígito numérico (0-9), sin puntos, guiones ni texto adicional. Si no lo encuentras o no es un único dígito numérico, devuelve null.

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "certificado_existencia": """Analiza este Certificado de Existencia y Representación Legal, Registro Público de Comercio o equivalente (dependiendo del país) y extrae la información solicitada adaptándote a los nombres y secciones locales:
- razon_social: razón social completa de la empresa
- tipo_persona: determina si el documento corresponde a una "Persona Jurídica" (sociedad/empresa) o "Persona Natural" (individuo). Búscalo en el encabezado, clasificación o cuerpo del documento. Valores posibles exactos: "Persona Jurídica" o "Persona Natural".
- tipo_identificacion: tipo de identificación de la empresa. Busca la etiqueta del campo de número tributario (ej. NIT, RUC, CUIT, RFC, etc). Si es un identificador de empresa asume "NIT" como valor genérico. Si no encuentras el tipo, devuelve "NIT" por defecto para empresas.
- nit: número de identificación tributaria o fiscal de la empresa (solo alfanuméricos, sin puntos, guiones ni dígito de verificación)
- representante_legal: nombre completo del representante legal, administrador o gerente
- cedula_representante: número de identificación (cédula, DNI, pasaporte) del representante legal (solo caracteres alfanuméricos o digitos)
- termino_duracion: vigencia o término de duración de la sociedad extraída del documento. Si es una fecha específica devuelve formato YYYY-MM-DD; si es indefinida devuelve "INDEFINIDA".
- fecha_documento: fecha de expedición del certificado en formato YYYY-MM-DD
- direccion: dirección comercial, domicilio principal o sede social registrada
- municipio: municipio, ciudad o jurisdicción registrada
- correo: correo electrónico registrado
- telefono: teléfono comercial registrado (solo dígitos)
- objeto_social: descripción principal del objeto social (resumido)

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "estados_financieros": """Analiza estos estados financieros (pueden ser de cualquier país) y extrae las siguientes cifras del último año reportado:
- razon_social: nombre o razón social de la empresa que presenta los estados financieros (búscalo en el encabezado o membrete del documento)
- nit: Identificador tributario o fiscal de la empresa (solo alfanuméricos, sin puntos, guiones ni dígito de verificación). Búscalo en el encabezado, membrete o carátula del documento.
- nombre_representante: nombre completo del representante legal o firmante principal del documento. Búscalo en la sección de firmas, en el bloque del representante legal, o en la carátula. Si no aparece explícitamente, devuelve null.
- cedula_representante: número de documento de identidad del representante legal o firmante. Solo caracteres alfanuméricos, sin puntos, guiones ni espacios. Búscalo junto al nombre del representante en la sección de firmas o en el bloque del representante legal. Si no aparece explícitamente, devuelve null.
- total_activos: valor numérico del total de activos (solo número, sin separadores)
- total_pasivos: valor numérico del total de pasivos (solo número)
- patrimonio: valor numérico del patrimonio neto (solo número)
- ingresos: valor numérico del total de ingresos operacionales (solo número)
- egresos: valor numérico del total de gastos/costos (solo número)
- anio_reporte: año del reporte (número entero, ej: 2025)
- cifras_en: unidad de las cifras ("pesos", "dólares", "miles", "millones", etc.)
- firmado: true si el documento tiene firma visible, false si no
- tiene_comparativo: true si muestra datos de 2 años, false si solo un año
- firma_revisor_fiscal: true si hay firma de revisor fiscal, auditor o contador público independiente, false si no

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "declaracion_renta": """Analiza esta Declaración de Renta o de Impuestos sobre la Renta (de cualquier país) y extrae:
- razon_social: nombre o razón social del declarante
- nit: identificador tributario o fiscal del declarante (solo alfanuméricos)
- anio_gravable: año gravable o fiscal declarado (número entero)
- total_patrimonio_bruto: valor numérico (solo número)
- total_patrimonio_liquido: valor numérico (solo número)
- total_ingresos_brutos: valor numérico (solo número)

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "referencias_bancarias": """Analiza esta certificación/referencia bancaria (de cualquier país) y extrae:
- entidad: nombre del banco o entidad financiera
- tipo_cuenta: tipo de producto (ahorros, corriente, etc.)
- numero_cuenta: número de cuenta (parcial o completo)
- titular: nombre del titular de la cuenta
- nit: Identificador tributario o fiscal del titular (solo alfanuméricos). Búscalo en el cuerpo de la carta bancaria; puede no estar presente.
- fecha_documento: fecha de expedición en formato YYYY-MM-DD

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",
}
