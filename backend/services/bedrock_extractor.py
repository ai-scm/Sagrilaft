"""
Extractor de datos de documentos usando AWS Bedrock (Claude).
Envía PDFs/imágenes a Claude para OCR + extracción estructurada.

Usa asyncio.to_thread para no bloquear el event loop de FastAPI
con las llamadas síncronas de boto3.
"""

import asyncio
import base64
import json
import logging
import mimetypes
from typing import Any, Dict

from services.contracts import ExtractionResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Prompts de Extracción por Tipo de Documento
# ═══════════════════════════════════════════════════════════════

EXTRACTION_PROMPTS: Dict[str, str] = {
    "cedula_representante": """Analiza este documento de identificación colombiano y extrae exactamente los siguientes campos:
- tipo_documento: tipo de documento tal como aparece en el encabezado. Normaliza tildes: "CÉDULA DE CIUDADANÍA" → "CEDULA DE CIUDADANIA". Valores posibles: "CEDULA DE CIUDADANIA", "CEDULA DE EXTRANJERIA", "PASAPORTE".
- nombre: nombre completo de la persona (nombres y apellidos)
- numero_documento: número del documento (solo dígitos, sin puntos ni espacios)
- fecha_expedicion: fecha de expedición en formato YYYY-MM-DD
- lugar_expedicion: ciudad o municipio de expedición
- fecha_nacimiento: fecha de nacimiento en formato DD-MMM-AAAA usando abreviaturas en español en mayúsculas. Ejemplos: "15-AGO-1990", "03-ENE-2001", "22-DIC-1985". Tabla de meses: 01=ENE, 02=FEB, 03=MAR, 04=ABR, 05=MAY, 06=JUN, 07=JUL, 08=AGO, 09=SEP, 10=OCT, 11=NOV, 12=DIC.
- lugar_nacimiento: ciudad o municipio de nacimiento tal como aparece en el documento

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "rut": """Analiza este documento RUT (Registro Único Tributario) de la DIAN Colombia y extrae:
- razon_social: nombre o razón social completa
- nit: número de identificación tributaria (solo dígitos, sin puntos ni guiones)
- actividades_economicas: lista de códigos CIIU con descripción (array de strings)
- fecha_documento: fecha del documento en formato YYYY-MM-DD
- direccion: dirección registrada
- correo: correo electrónico registrado

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "certificado_existencia": """Analiza este Certificado de Existencia y Representación Legal de Cámara de Comercio y extrae:
- razon_social: razón social completa de la empresa
- nit: NIT de la empresa (solo dígitos, sin puntos ni guiones)
- representante_legal: nombre completo del representante legal
- cedula_representante: número de cédula del representante legal (solo dígitos)
- fecha_documento: fecha de expedición del certificado en formato YYYY-MM-DD
- direccion: dirección comercial registrada
- municipio: municipio o ciudad registrada en la sección UBICACIÓN del certificado
- objeto_social: descripción del objeto social (resumido)

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",

    "estados_financieros": """Analiza estos estados financieros y extrae las siguientes cifras del último año reportado:
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
- fecha_documento: fecha de expedición en formato YYYY-MM-DD

Responde SOLO con un JSON válido, sin texto adicional. Si no puedes leer algún campo, usa null.""",
}

# Mapping de tipo documento a campos de formulario para pre-fill
PREFILL_MAPPING: Dict[str, Dict[str, str]] = {
    "rut": {
        "razon_social": "razon_social",
        "nit": "numero_identificacion",
        "direccion": "direccion",
        "correo": "correo",
    },
    "certificado_existencia": {
        "razon_social": "razon_social",
        "nit": "numero_identificacion",
        "representante_legal": "nombre_representante",
        "cedula_representante": "numero_doc_representante",
        "direccion": "direccion",
        "municipio": "ciudad",
    },
    "cedula_representante": {
        "nombre": "nombre_representante",
        "numero_documento": "numero_doc_representante",
        "tipo_documento": "tipo_doc_representante",
        "fecha_nacimiento": "fecha_nacimiento",
        "lugar_nacimiento": "ciudad_nacimiento",
        "fecha_expedicion": "fecha_expedicion",
        "lugar_expedicion": "ciudad_expedicion",
    },
    "estados_financieros": {
        "total_activos": "total_activos",
        "total_pasivos": "total_pasivos",
        "patrimonio": "patrimonio",
        "ingresos": "ingresos_mensuales",
        "egresos": "egresos_mensuales",
    },
}


class BedrockExtractor:
    """
    Extractor real usando AWS Bedrock con Claude.

    Lee archivos locales (PDF/imagen), los envía a Claude via Bedrock,
    y parsea la respuesta JSON estructurada.

    Nota: boto3 es síncrono, se wrappea con asyncio.to_thread
    para no bloquear el event loop de FastAPI.
    """

    def __init__(self, region: str, model_id: str, max_tokens: int = 4096):
        import boto3
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id
        self._max_tokens = max_tokens

    async def extract(
        self,
        file_path: str,
        document_type: str,
    ) -> ExtractionResult:
        """Extrae datos de un documento usando Claude via Bedrock."""
        prompt = EXTRACTION_PROMPTS.get(document_type)
        if not prompt:
            return ExtractionResult(
                extraido=False,
                mensaje=f"Tipo de documento '{document_type}' no tiene prompt de extracción configurado."
            )

        try:
            # Ejecutar la llamada síncrona de boto3 en un thread separado
            return await asyncio.to_thread(
                self._extract_sync, file_path, document_type, prompt
            )
        except ImportError:
            logger.error("boto3 no está instalado. Instale con: pip install boto3")
            return ExtractionResult(
                extraido=False,
                mensaje="boto3 no instalado. Ejecute: pip install boto3"
            )
        except Exception as e:
            logger.error("Error extrayendo datos de %s: %s", file_path, str(e))
            return ExtractionResult(
                extraido=False,
                mensaje=f"Error al procesar documento: {str(e)}"
            )

    def _extract_sync(
        self,
        file_path: str,
        document_type: str,
        prompt: str,
    ) -> ExtractionResult:
        """Llamada síncrona a Bedrock usando la API Converse Universal."""
        file_content, media_type = self._read_file(file_path)

        logger.info(
            "Invocando Bedrock (Converse API): modelo=%s, tipo=%s, tamaño=%d bytes",
            self._model_id, document_type, len(file_content),
        )

        file_extension = "pdf"
        if media_type.startswith("image/"):
            # png, jpeg, webp
            file_extension = media_type.split("/")[-1]
            if file_extension == "jpeg":
                file_extension = "jpeg"
            content_block = {
                "image": {
                    "format": file_extension,
                    "source": {"bytes": file_content}
                }
            }
        else:
            # document: pdf, csv, doc, docx, xls, xlsx, html, txt, md
            content_block = {
                "document": {
                    "name": "doc_" + document_type,
                    "format": "pdf",
                    "source": {"bytes": file_content}
                }
            }

        response = self._client.converse(
            modelId=self._model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        content_block,
                        {"text": prompt}
                    ]
                }
            ],
            inferenceConfig={
                "maxTokens": self._max_tokens,
                "temperature": 0.0,
            }
        )

        extracted_text = response["output"]["message"]["content"][0]["text"]

        # Parsear JSON de la respuesta de la IA
        datos = self._parse_json_response(extracted_text)

        logger.info(
            "Extracción exitosa: tipo=%s, campos_extraidos=%s",
            document_type, list(datos.keys()),
        )

        return ExtractionResult(
            extraido=True,
            datos=datos,
            mensaje=f"Datos extraídos exitosamente de {document_type}",
            confianza=0.90,
        )


    def _read_file(self, file_path: str) -> tuple[bytes, str]:
        """Lee un archivo y determina su tipo MIME."""
        with open(file_path, "rb") as f:
            content = f.read()

        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/pdf"

        return content, mime_type

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """Parsea la respuesta JSON de Claude, tolerando markdown."""
        cleaned = text.strip()

        # Remover bloques ```json ... ```
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        return json.loads(cleaned)

    @staticmethod
    def get_prefill_fields(
        document_type: str,
        extracted_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mapea datos extraídos a campos del formulario para pre-llenado.
        Retorna solo los campos que tienen valor no-nulo.
        """
        mapping = PREFILL_MAPPING.get(document_type, {})
        prefill = {}
        for doc_field, form_field in mapping.items():
            value = extracted_data.get(doc_field)
            if value is not None:
                prefill[form_field] = value
        return prefill
