"""
Extractor de datos de documentos usando AWS Bedrock (Claude).

Envía PDFs/imágenes a Claude para OCR + extracción estructurada.
Usa asyncio.to_thread para no bloquear el event loop de FastAPI
con las llamadas síncronas de boto3.
"""

import asyncio
import io
import json
import logging
import mimetypes
import os
from typing import Any, Dict, Tuple

import boto3
from botocore.config import Config
from pypdf import PdfReader, PdfWriter

from domain.contratos import ResultadoExtraccion
from domain.utils.mapeo_campos import mapear_campos_para_formulario
from infrastructure.emf_logger import emitir_metrica_emf

logger = logging.getLogger(__name__)


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

    # Tiempo máximo de espera para que Bedrock complete la extracción de un PDF.
    # Claude Sonnet puede tardar entre 30 y 90 s en documentos complejos.
    # El valor debe ser menor al idleTimeout del ALB (60s típicamente) para que la
    # respuesta de error de boto3 llegue antes de que el gateway corte la conexión.
    _TIMEOUT_LECTURA_BEDROCK_SEGUNDOS: int = 90

    def __init__(self, region: str, modelo_id: str, max_tokens: int = 4096) -> None:

        configuracion_cliente = Config(
            connect_timeout=10,
            read_timeout=self._TIMEOUT_LECTURA_BEDROCK_SEGUNDOS,
            retries={
                "max_attempts": 3,
                "mode": "standard"  # Maneja cuotas (429) y fallas transitorias de IA con backoff
            },
        )
        self._cliente = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=configuracion_cliente,
        )
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
            error_str = str(error)
            logger.error("Error extrayendo datos de %s: %s", ruta_archivo, error_str)
            
            # Obfuscate AWS internal details for security
            if "endpoint URL" in error_str or "arn:aws" in error_str or "Read timeout" in error_str:
                mensaje_usuario = "El servidor de IA tardó demasiado en responder o está temporalmente indisponible. Por favor, valide e ingrese la información manualmente."
            else:
                mensaje_usuario = f"Error al procesar documento: El documento no pudo ser procesado por la IA. Por favor, valide e ingrese la información manualmente."

            return ResultadoExtraccion(
                extraido=False,
                mensaje=mensaje_usuario,
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
        
        # Emitir EMF Metric de tokens consumidos
        if "usage" in respuesta:
            emitir_metrica_emf(
                namespace="Sagrilaft/Negocio",
                dimensiones={"Servicio": "Bedrock", "ModeloId": self._modelo_id, "TipoDocumento": tipo_documento},
                metricas={
                    "BedrockInputTokens": respuesta["usage"].get("inputTokens", 0),
                    "BedrockOutputTokens": respuesta["usage"].get("outputTokens", 0)
                }
            )

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

    @classmethod
    def _leer_archivo(cls, ruta_archivo: str) -> Tuple[bytes, str]:
        """
        Lee el contenido binario de un archivo y determina su tipo MIME.
        Optimiza los documentos PDF reduciendo su tamaño.
        """
        tipo_mime = cls._determinar_tipo_mime(ruta_archivo)

        if tipo_mime == "application/pdf":
            contenido = cls._obtener_pdf_optimizado(ruta_archivo)
        else:
            with open(ruta_archivo, "rb") as archivo:
                contenido = archivo.read()

        return contenido, tipo_mime

    @staticmethod
    def _determinar_tipo_mime(ruta_archivo: str) -> str:
        """Determina el tipo MIME basándose en la extensión del archivo."""
        tipo_mime, _ = mimetypes.guess_type(ruta_archivo)
        if tipo_mime is None:
            return "application/pdf" if ruta_archivo.lower().endswith('.pdf') else "application/octet-stream"
        return tipo_mime

    @classmethod
    def _obtener_pdf_optimizado(cls, ruta_archivo: str, max_paginas: int = 7) -> bytes:
        """Devuelve el PDF recortado si excede el límite, o el original si hay error."""
        try:
            return cls._recortar_primeras_paginas_pdf(ruta_archivo, max_paginas)
        except Exception as error:
            logger.warning(
                "No se pudo optimizar el PDF %s (%s). Se usará el original completo.",
                os.path.basename(ruta_archivo),
                str(error),
            )
            with open(ruta_archivo, "rb") as archivo:
                return archivo.read()

    @staticmethod
    def _recortar_primeras_paginas_pdf(ruta_archivo: str, max_paginas: int) -> bytes:
        """
        Lee el PDF y recorta las primeras páginas.
        Lanza excepción si pypdf no está disponible o el archivo es inválido.
        """
        reader = PdfReader(ruta_archivo)
        total_paginas = len(reader.pages)

        if total_paginas <= max_paginas:
            with open(ruta_archivo, "rb") as archivo:
                return archivo.read()

        logger.info(
            "Optimizando PDF %s: Recortando de %d a %d páginas para extracción IA.",
            os.path.basename(ruta_archivo),
            total_paginas,
            max_paginas,
        )
        
        writer = PdfWriter()
        for i in range(max_paginas):
            writer.add_page(reader.pages[i])

        buffer_salida = io.BytesIO()
        writer.write(buffer_salida)
        return buffer_salida.getvalue()

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
