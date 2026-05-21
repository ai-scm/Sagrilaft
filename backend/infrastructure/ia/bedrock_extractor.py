"""
Extractor de datos de documentos usando AWS Bedrock (Claude).

Envía PDFs/imágenes a Claude para OCR + extracción estructurada.
Usa asyncio.to_thread para no bloquear el event loop de FastAPI
con las llamadas síncronas de boto3.
"""

import asyncio
import json
import logging
import mimetypes
from typing import Any, Dict, Tuple

from core.contratos import ResultadoExtraccion
from services.formulario.prellenado import mapear_campos_para_formulario

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Prompts de extracción por tipo de documento
# ═══════════════════════════════════════════════════════════════

PROMPTS_EXTRACCION: Dict[str, str] = {
    "cedula_representante": """Analiza este documento de identificación colombiano y extrae exactamente los siguientes campos:
- tipo_documento: tipo de documento tal como aparece en el encabezado. Normaliza tildes: "CÉDULA DE CIUDADANÍA" → "CEDULA DE CIUDADANIA". Valores posibles: "CEDULA DE CIUDADANIA", "CEDULA DE EXTRANJERIA", "PASAPORTE".
- nombre: nombre completo de la persona (nombres y apellidos)
- numero_documento: número del documento (solo dígitos, sin puntos ni espacios)
- fecha_expedicion: fecha de expedición en formato YYYY-MM-DD
- lugar_expedicion: ciudad o municipio de expedición
- fecha_nacimiento: fecha de nacimiento en formato YYYY-MM-DD. Ejemplo: "1990-08-15".
- lugar_nacimiento: ciudad o municipio de nacimiento tal como aparece en el documento

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "rut": """Analiza este documento RUT (Registro Único Tributario) de la DIAN Colombia y extrae:
- razon_social: nombre o razón social completa
- nit: número de identificación tributaria (solo dígitos, sin puntos ni guiones)
- actividades_economicas: lista de códigos CIIU con descripción (array de strings)
- codigo_ica: código de la actividad principal para el Impuesto de Industria y Comercio (ICA). Búscalo en la sección "CLASIFICACION" → subsección "Actividad Principal" → campo "46. Codigo". Devuelve solo el número, sin texto adicional.
- tipo_persona: tipo de persona de la sección "CLASIFICACIÓN E INFORMACIÓN BÁSICA DE LA EMPRESA" → pregunta "24. Tipo de contribuyente" → campo "Tipo de Persona". Valores posibles exactos: "Persona Jurídica" o "Persona Natural".
- nombre_representante: nombre completo del representante legal. Búscalo en la sección "REPRESENTACIÓN" y concatena los campos en este orden: "106. Primer nombre" + "107. Otros nombres" (si existe) + "104. Primer apellido" + "105. Segundo apellido". Devuelve una sola cadena con los valores separados por espacio, omitiendo los que sean nulos.
- fecha_documento: fecha del documento en formato YYYY-MM-DD
- direccion: dirección registrada
- correo: correo electrónico registrado
- telefono: número de teléfono registrado (solo dígitos, sin espacios ni guiones)
- cedula_representante: número de identificación del representante legal. Búscalo en la sección "REPRESENTACIÓN" → campo "101. Número de identificación". REGLAS ESTRICTAS: (1) El campo "100. Tipo de documento" contiene SOLO un código corto de 2 dígitos (13=CC, 22=CE, 31=NIT, 41=PAS) — ese código NUNCA forma parte del número de identificación. (2) Lee el número que aparece EXCLUSIVAMENTE después del label "101." — ignorando completamente la fila del "100.". (3) Si el valor que extrajiste empieza por 13, 22, 31 o 41 seguido de más dígitos, esos 2 primeros dígitos son el código del tipo de documento que se coló accidentalmente — descártalos y devuelve solo los dígitos restantes. (4) Devuelve únicamente dígitos, sin espacios ni guiones. Si no encuentras el campo 101, devuelve null.
- clasificacion_dv: dígito de verificación del NIT. Búscalo en la sección "IDENTIFICACIÓN" → campo "6. DV". Devuelve ÚNICAMENTE el dígito numérico (0-9), sin puntos, guiones ni texto adicional. Si no lo encuentras o no es un único dígito numérico, devuelve null.

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "certificado_existencia": """Analiza este Certificado de Existencia y Representación Legal de Cámara de Comercio y extrae:
- razon_social: razón social completa de la empresa
- tipo_persona: determina si el documento corresponde a una "Persona Jurídica" o "Persona Natural". Búscalo en el encabezado del certificado, en la sección de clasificación o en frases como "La persona jurídica..." o "La persona natural...". Valores posibles exactos: "Persona Jurídica" o "Persona Natural".
- tipo_identificacion: tipo de identificación de la empresa según la sección "NOMBRE, IDENTIFICACIÓN Y DOMICILIO". Busca la etiqueta del campo de número (ej: "NIT", "Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte"). Normaliza SIEMPRE a uno de estos valores exactos: "NIT", "CC", "CE", "PAS". Reglas de normalización: si el documento dice "NIT" o "Número de Identificación Tributaria" → devuelve "NIT"; si dice "Cédula de ciudadanía" o "Cedula de ciudadania" → devuelve "CC"; si dice "Cédula de extranjería" o "Cedula de extranjeria" → devuelve "CE"; si dice "Pasaporte" → devuelve "PAS". Si no encuentras el tipo, devuelve "NIT" como valor por defecto para personas jurídicas.
- nit: número de identificación de la empresa en la sección "NOMBRE, IDENTIFICACIÓN Y DOMICILIO" (solo dígitos, sin puntos, guiones ni dígito de verificación)
- representante_legal: nombre completo del representante legal
- cedula_representante: número de cédula del representante legal (solo dígitos)
- termino_duracion: vigencia de la empresa extraída de la sección "TÉRMINO DE DURACIÓN" o de frases como "su duración es hasta el [FECHA]" o "su duración es indefinida". Si es una fecha específica devuelve formato YYYY-MM-DD; si es indefinida devuelve "INDEFINIDA".
- fecha_documento: fecha de expedición del certificado en formato YYYY-MM-DD
- direccion: dirección comercial registrada
- municipio: municipio o ciudad registrada en la sección UBICACIÓN del certificado
- correo: correo electrónico registrado en la sección UBICACIÓN del certificado (campo "Correo electrónico")
- telefono: teléfono comercial registrado en la sección UBICACIÓN del certificado (campo "Teléfono comercial 1", solo dígitos)
- objeto_social: descripción del objeto social (resumido)

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "estados_financieros": """Analiza estos estados financieros y extrae las siguientes cifras del último año reportado:
- razon_social: nombre o razón social de la empresa que presenta los estados financieros (búscalo en el encabezado o membrete del documento)
- nit: NIT de la empresa (solo dígitos, sin puntos, guiones ni dígito de verificación). Búscalo en el encabezado, membrete o carátula del documento.
- nombre_representante: nombre completo del representante legal o firmante principal del documento. Búscalo en la sección de firmas, en el bloque del representante legal, o en la carátula. Si no aparece explícitamente, devuelve null.
- cedula_representante: número de documento de identidad (cédula, pasaporte, etc.) del representante legal o firmante. Solo caracteres alfanuméricos, sin puntos, guiones ni espacios. Búscalo junto al nombre del representante en la sección de firmas o en el bloque del representante legal. Si no aparece explícitamente, devuelve null.
- total_activos: valor numérico del total de activos (solo número, sin separadores)
- total_pasivos: valor numérico del total de pasivos (solo número)
- patrimonio: valor numérico del patrimonio neto (solo número)
- ingresos: valor numérico del total de ingresos operacionales (solo número)
- egresos: valor numérico del total de gastos/costos (solo número)
- anio_reporte: año del reporte (número entero, ej: 2025)
- cifras_en: unidad de las cifras ("pesos", "miles", "millones")
- firmado: true si el documento tiene firma visible, false si no
- tiene_comparativo: true si muestra datos de 2 años, false si solo un año
- firma_revisor_fiscal: true si hay firma del revisor fiscal, false si no

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "declaracion_renta": """Analiza esta Declaración de Renta colombiana y extrae:
- razon_social: nombre o razón social del declarante
- nit: NIT del declarante (solo dígitos)
- anio_gravable: año gravable declarado (número entero)
- total_patrimonio_bruto: valor numérico (solo número)
- total_patrimonio_liquido: valor numérico (solo número)
- total_ingresos_brutos: valor numérico (solo número)

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "referencias_bancarias": """Analiza esta certificación/referencia bancaria y extrae:
- entidad: nombre del banco o entidad financiera
- tipo_cuenta: tipo de producto (ahorros, corriente, etc.)
- numero_cuenta: número de cuenta (parcial o completo)
- titular: nombre del titular de la cuenta
- nit: NIT del titular (solo dígitos, sin puntos, guiones ni dígito de verificación). Búscalo en el cuerpo de la carta bancaria; puede no estar presente.
- fecha_documento: fecha de expedición en formato YYYY-MM-DD

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",
}


# ═══════════════════════════════════════════════════════════════
# Extractor
# ═══════════════════════════════════════════════════════════════

class ExtractorBedrock:
    """
    Extractor de datos usando AWS Bedrock con Claude.

    Lee archivos locales (PDF/imagen), los envía a Claude vía Bedrock
    y parsea la respuesta JSON estructurada.

    Nota: boto3 es síncrono; se envuelve con asyncio.to_thread
    para no bloquear el event loop de FastAPI.

    DIP : implementa ExtractorImp — el orquestador depende de la abstracción,
          no de esta clase directamente.
    """

    def __init__(self, region: str, modelo_id: str, max_tokens: int = 4096) -> None:
        import boto3
        self._cliente = boto3.client("bedrock-runtime", region_name=region)
        self._modelo_id = modelo_id
        self._max_tokens = max_tokens

    async def extraer(
        self,
        ruta_archivo: str,
        tipo_documento: str,
    ) -> ResultadoExtraccion:
        """
        Extrae datos estructurados de un documento usando Claude vía Bedrock.

        Args:
            ruta_archivo:    Ruta local al archivo PDF o imagen.
            tipo_documento:  Clave del documento (ej. 'rut', 'cedula_representante').

        Returns:
            ResultadoExtraccion con los datos parseados o el error encontrado.
        """
        prompt = PROMPTS_EXTRACCION.get(tipo_documento)
        if not prompt:
            return ResultadoExtraccion(
                extraido=False,
                mensaje=f"Tipo de documento '{tipo_documento}' no tiene prompt de extracción configurado.",
            )

        try:
            return await asyncio.to_thread(
                self._extraer_sincronico, ruta_archivo, tipo_documento, prompt
            )
        except ImportError:
            logger.error("boto3 no está instalado. Instale con: pip install boto3")
            return ResultadoExtraccion(
                extraido=False,
                mensaje="boto3 no instalado. Ejecute: pip install boto3",
            )
        except Exception as error:
            logger.error("Error extrayendo datos de %s: %s", ruta_archivo, str(error))
            return ResultadoExtraccion(
                extraido=False,
                mensaje=f"Error al procesar documento: {str(error)}",
            )

    # ─── Métodos privados ─────────────────────────────────────────────────────

    def _extraer_sincronico(
        self,
        ruta_archivo: str,
        tipo_documento: str,
        prompt: str,
    ) -> ResultadoExtraccion:
        """
        Llamada síncrona a Bedrock usando la API Converse Universal.

        SRP : se ocupa únicamente de invocar el modelo y parsear la respuesta.
        """
        contenido_archivo, tipo_mime = self._leer_archivo(ruta_archivo)

        logger.info(
            "Invocando Bedrock (Converse API): modelo=%s, tipo=%s, tamaño=%d bytes",
            self._modelo_id, tipo_documento, len(contenido_archivo),
        )

        bloque_contenido = self._construir_bloque_contenido(
            tipo_mime, contenido_archivo, tipo_documento
        )

        respuesta = self._cliente.converse(
            modelId=self._modelo_id,
            messages=[
                {
                    "role": "user",
                    "content": [bloque_contenido, {"text": prompt}],
                }
            ],
            inferenceConfig={
                "maxTokens": self._max_tokens,
                "temperature": 0.0,
            },
        )

        texto_extraido = respuesta["output"]["message"]["content"][0]["text"]
        datos = self._parsear_respuesta_json(texto_extraido)

        logger.info(
            "Extracción exitosa: tipo=%s, campos_extraidos=%s",
            tipo_documento, list(datos.keys()),
        )

        return ResultadoExtraccion(
            extraido=True,
            datos=datos,
            mensaje=f"Datos extraídos exitosamente de {tipo_documento}",
            confianza=0.90,
        )

    @staticmethod
    def _construir_bloque_contenido(
        tipo_mime: str,
        contenido: bytes,
        tipo_documento: str,
    ) -> Dict[str, Any]:
        """
        Construye el bloque de contenido para la API Converse de Bedrock,
        diferenciando entre imágenes y documentos PDF.

        Args:
            tipo_mime:      MIME type del archivo (ej. 'image/png', 'application/pdf').
            contenido:      Bytes del archivo.
            tipo_documento: Clave de tipo (usada como nombre en bloques de documento).

        Returns:
            Diccionario con la estructura esperada por la API Converse.
        """
        if tipo_mime.startswith("image/"):
            extension = tipo_mime.split("/")[-1]
            return {
                "image": {
                    "format": extension,
                    "source": {"bytes": contenido},
                }
            }
        return {
            "document": {
                "name": f"doc_{tipo_documento}",
                "format": "pdf",
                "source": {"bytes": contenido},
            }
        }

    @staticmethod
    def _leer_archivo(ruta_archivo: str) -> Tuple[bytes, str]:
        """
        Lee el contenido binario de un archivo y determina su tipo MIME.

        Returns:
            Tupla (contenido_bytes, tipo_mime).
        """
        with open(ruta_archivo, "rb") as archivo:
            contenido = archivo.read()

        tipo_mime, _ = mimetypes.guess_type(ruta_archivo)
        if tipo_mime is None:
            tipo_mime = "application/pdf"

        return contenido, tipo_mime

    @staticmethod
    def _parsear_respuesta_json(texto: str) -> Dict[str, Any]:
        """
        Parsea la respuesta JSON de Claude con tolerancia a variaciones de formato.

        Maneja dos casos conocidos en los que Claude no devuelve JSON puro:
        1. Bloque markdown: ```json ... ``` — se eliminan las líneas de fence.
        2. Texto trailing: JSON válido seguido de notas o aclaraciones del modelo
           ("Extra data" en json.loads) — se extrae solo el primer objeto JSON.

        raw_decode() parsea el primer valor JSON completo y devuelve el índice
        donde termina, ignorando cualquier contenido posterior.
        """
        limpio = texto.strip()
        logger.debug("Respuesta cruda de Claude:\n%s", limpio[:800])
        if limpio.startswith("```"):
            lineas = limpio.split("\n")
            lineas = [l for l in lineas if not l.strip().startswith("```")]
            limpio = "\n".join(lineas).strip()

        inicio = limpio.find("{")
        if inicio == -1:
            raise ValueError("No se encontró ningún objeto JSON en la respuesta del modelo.")

        datos, _ = json.JSONDecoder().raw_decode(limpio, inicio)
        return datos

    @staticmethod
    def obtener_campos_prellenado(
        tipo_documento: str,
        datos_extraidos: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mapea datos extraídos a campos del formulario para pre-llenado.

        DRY: delega a mapear_campos_para_formulario (services/prellenado.py),
        que es la fuente única de verdad para este mapeo.

        Args:
            tipo_documento:  Clave del tipo de documento procesado.
            datos_extraidos: Diccionario con los campos extraídos por IA.

        Returns:
            Diccionario con los campos del formulario y sus valores sugeridos.
        """
        return mapear_campos_para_formulario(tipo_documento, datos_extraidos)
