"""Contratos F5.1. No reciben archivos ni ejecutan operaciones administrativas."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from domain.listas.catalogo_fuentes import fuente_de_formato
from domain.listas.contratos import DTO, Texto, ClaveIdempotencia

Huella = Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")]
Revision = Annotated[int, Field(strict=True, ge=0, le=9223372036854775807)]
TipoOperacion = Literal["ACTIVACION", "REVERSION"]
EstadoIntento = Literal["PENDIENTE", "EN_CURSO", "COMPLETADO", "FALLIDO"]
FaseImportacion = Literal["VALIDACION", "IMPORTACION", "COMPROBACION", "SELLADO"]
# Códigos de fuente/formato: abiertos a cualquier fuente registrada en el
# catálogo de dominio (domain.listas.catalogo_fuentes), no a una lista fija de
# valores de OFAC. El `model_validator` de abajo es quien exige que el código
# corresponda a una fuente realmente registrada.
CodigoFuente = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]
CodigoFormato = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")]


class RecepcionPropuesta(DTO):
    fuente: CodigoFuente
    formato: CodigoFormato
    nombre_original: Texto
    procedencia: Annotated[str, StringConstraints(min_length=1, max_length=2048)]
    descargado_en: AwareDatetime | None = None
    huella_declarada: Huella
    clave: ClaveIdempotencia


    @model_validator(mode='after')
    def comprobar_fuente_formato(self):
        fuente = fuente_de_formato(self.formato)
        if fuente is None or fuente.codigo != self.fuente:
            raise ValueError('Fuente, formato y procedencia incompatibles')
        if fuente.oficial:
            if self.procedencia != fuente.procedencia_oficial:
                raise ValueError('Fuente, formato y procedencia incompatibles')
            if self.descargado_en is None:
                raise ValueError('La recepción de una fuente oficial requiere fecha de descarga declarada')
        elif self.procedencia != 'FIXTURE_LOCAL':
            raise ValueError('Fuente, formato y procedencia incompatibles')
        return self


class ComparacionPropuesta(DTO):
    fuente_id: UUID
    destino_id: UUID
    revision_esperada: Revision
    clave: ClaveIdempotencia


class SolicitudAdministrativa(DTO):
    comparacion_id: UUID
    politica_id: UUID
    tipo: TipoOperacion
    motivo: Texto
    clave: ClaveIdempotencia


class DecisionAdministrativa(DTO):
    solicitud_id: UUID
    decision: Literal["APROBADA", "RECHAZADA"]
    motivo: Texto
    clave: ClaveIdempotencia


class EjecucionAdministrativa(DTO):
    solicitud_id: UUID
    aprobacion_id: UUID
    revision_esperada: Revision
    clave: ClaveIdempotencia


class OperacionMotivada(DTO):
    objeto_id: UUID
    motivo: Texto
    clave: ClaveIdempotencia


class AdmisionAdministrativa(DTO):
    recepcion_id: UUID
    intento_id: UUID


class ProgresoImportacion(DTO):
    intento_id: UUID
    estado: EstadoIntento
    fase: FaseImportacion
    registros_confirmados: Annotated[int, Field(strict=True, ge=0, le=2147483647)]
    codigo_error: Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")] | None = None

    @model_validator(mode="after")
    def comprobar_progreso(self):
        if self.estado == "PENDIENTE" and (self.fase != "VALIDACION" or self.registros_confirmados):
            raise ValueError("Un intento pendiente todavía no tiene registros confirmados")
        if self.estado == "COMPLETADO" and (self.fase != "SELLADO" or self.registros_confirmados == 0):
            raise ValueError("Completar exige sellado y registros confirmados")
        if (self.estado == "FALLIDO") != (self.codigo_error is not None):
            raise ValueError("Solo un intento fallido debe incluir un código de error")
        return self


class PerfilEnsayo(DTO):
    """Valores de ensayo, no dimensionamiento certificado para OFAC."""
    codigo: Literal["f5-sintetico-v1"] = "f5-sintetico-v1"
    recibido_bytes: Literal[104857600] = 104857600
    expandido_bytes: Literal[524288000] = 524288000
    entradas_zip: Literal[20] = 20
    relacion_compresion: Literal[100] = 100
    profundidad_xml: Literal[64] = 64
    texto_bytes: Literal[1048576] = 1048576
    atributo_bytes: Literal[8192] = 8192
    elementos_xml: Literal[2000000] = 2000000
    memoria_bytes: Literal[1073741824] = 1073741824
    disco_temporal_bytes: Literal[2147483648] = 2147483648
    partes_multipart: Literal[8] = 8
    campos_bytes: Literal[16384] = 16384
    carga_segundos: Literal[300] = 300
    validacion_segundos: Literal[300] = 300
    intento_segundos: Literal[1800] = 1800
    recuperaciones: Literal[3] = 3
    cargas_actor: Literal[1] = 1
    cargas_globales: Literal[2] = 2
    trabajadores_globales: Literal[1] = 1
    lote_registros: Literal[1000] = 1000
    comparacion_registros: Literal[10000] = 10000
    comparacion_bytes: Literal[16777216] = 16777216
    concesion_segundos: Literal[120] = 120
    latido_segundos: Literal[30] = 30


class PerfilOfacLocal(PerfilEnsayo):
    """Límites locales para el archivo autorizado; no certifican capacidad productiva."""
    codigo: Literal['ofac-advanced-local-v2'] = 'ofac-advanced-local-v2'
    lote_registros: Literal[100] = 100
    comparacion_registros: Literal[50000] = 50000
    comparacion_bytes: Literal[134217728] = 134217728
    recibido_bytes: Literal[268435456] = 268435456
    disco_temporal_bytes: Literal[4294967296] = 4294967296
    elementos_xml: Literal[10000000] = 10000000
    memoria_bytes: Literal[2147483648] = 2147483648


class EntradaArchivoValidada(DTO):
    nombre: Annotated[str, StringConstraints(min_length=1, max_length=65535)]
    sha256: Huella
    tamano: Annotated[int, Field(strict=True, ge=0)]
    principal: bool


class InformeValidacionArchivo(DTO):
    """Resultado de F5.3; VALIDO no significa importado ni activo."""
    resultado: Literal['VALIDO', 'INVALIDO']
    codigo: Annotated[str, StringConstraints(pattern=r'^[A-Z][A-Z0-9_]*$', max_length=64)] | None = None
    version_validador: str
    # Código de perfil de límites (ver `PerfilEnsayo.codigo`/`PerfilOfacLocal.codigo`):
    # abierto a cualquier perfil que una fuente declare, no cerrado a los de OFAC.
    perfil: Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9-]*$', max_length=64)]
    oficial: bool
    original_sha256: Huella
    esquema_sha256: Huella
    formato: CodigoFormato
    publicada_en: str | None = None
    origen_fecha: str = 'DESCONOCIDA'
    contenido_sha256: Huella | None = None
    contenido_tamano: Annotated[int, Field(strict=True, gt=0)] | None = None
    registros: Annotated[int, Field(strict=True, gt=0)] | None = None
    elementos: Annotated[int, Field(strict=True, gt=0)] | None = None
    entradas: tuple[EntradaArchivoValidada, ...] = ()
    lxml: tuple[int, ...] | None = None
    libxml: tuple[int, ...] | None = None

    @model_validator(mode='after')
    def comprobar_resultado(self):
        if self.resultado == 'VALIDO':
            if self.codigo is not None or any(valor is None for valor in (
                    self.contenido_sha256, self.contenido_tamano, self.registros, self.elementos)):
                raise ValueError('Validación correcta requiere contenido y conteos completos')
        elif self.codigo is None:
            raise ValueError('Validación fallida requiere código de error')
        return self
