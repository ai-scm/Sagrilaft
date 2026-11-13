"""Catálogos declarativos y versionados; no normalizan números ni buscan registros."""
import hashlib
import json

from pydantic import Field, model_validator

from .contratos import Codigo, DTO, Pais
from .datos_busqueda import CalidadDato, TextoDato

# ISO 3166-1 alpha-2, las 250 entradas que ofrecen los selectores de país del formulario
# (paquete `i18n-iso-countries`, idéntico al que usa `country-state-city`; verificado que
# ambos paquetes del frontend declaran exactamente este mismo conjunto, sin diferencias).
# Ningún código se acepta por "parecer" válido: debe estar en esta lista exacta.
PAISES_ISO_3166_1_ALPHA_2 = frozenset({
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX",
    "AZ", "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ",
    "BR", "BS", "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK",
    "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI", "FJ", "FK", "FM", "FO", "FR",
    "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS",
    "GT", "GU", "GW", "GY", "HK", "HM", "HN", "HR", "HT", "HU", "ID", "IE", "IL", "IM", "IN",
    "IO", "IQ", "IR", "IS", "IT", "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV",
    "LY", "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ",
    "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA", "NC", "NE", "NF", "NG", "NI",
    "NL", "NO", "NP", "NR", "NU", "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS", "RU", "RW", "SA", "SB", "SC",
    "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV",
    "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR",
    "TT", "TV", "TW", "TZ", "UA", "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "XK", "YE", "YT", "ZA", "ZM", "ZW",
})


class DefinicionIdentificador(DTO):
    tipo: Codigo
    esquema: Codigo
    alias: tuple[Codigo, ...] = ()
    jurisdiccion_requerida: bool
    multiples_por_sujeto: bool
    admite_digito_verificacion: bool = False
    normalizacion_version: Codigo = "conservacion-v1"

    @model_validator(mode="after")
    def exigir_codigos_canonicos(self):
        if any(codigo != codigo.strip().upper() for codigo in (self.tipo, *self.alias)):
            raise ValueError("Los códigos del catálogo deben ser canónicos en mayúsculas")
        return self


class EquivalenciaPais(DTO):
    declarado: TextoDato
    codigo: Pais


class CatalogoPreparacion(DTO):
    version: Codigo
    identificadores: tuple[DefinicionIdentificador, ...] = Field(min_length=1)
    paises: tuple[EquivalenciaPais, ...] = ()

    @model_validator(mode="after")
    def impedir_equivalencias_ambiguas(self):
        tipos = [n.strip().upper() for d in self.identificadores for n in (d.tipo, *d.alias)]
        paises = [p.declarado.strip().casefold() for p in self.paises]
        if len(set(tipos)) != len(tipos) or len(set(paises)) != len(paises):
            raise ValueError("El catálogo no puede asignar un valor declarado a dos equivalencias")
        return self

    def identificador(self, declarado):
        return next((d for d in self.identificadores
                     if declarado.strip().upper() in (d.tipo, *d.alias)), None)

    def pais(self, declarado):
        return next((p.codigo for p in self.paises
                     if p.declarado.strip().casefold() == declarado.strip().casefold()), None)

    @property
    def huella(self):
        datos = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(datos.encode()).hexdigest()


IDENTIFICADORES_INICIALES = (
    DefinicionIdentificador(tipo="CC", esquema="DOCUMENTO_NACIONAL",
                           jurisdiccion_requerida=True, multiples_por_sujeto=False),
    DefinicionIdentificador(tipo="CE", esquema="DOCUMENTO_EXTRANJERIA",
                           jurisdiccion_requerida=True, multiples_por_sujeto=False),
    # Pasaporte: OFAC publica algunos con espacios o guiones internos (p. ej. "09 1971993");
    # se quitan solo esos separadores, nunca letras ni dígitos.
    DefinicionIdentificador(tipo="PASAPORTE", alias=("PAS",), esquema="PASAPORTE",
                           jurisdiccion_requerida=True, multiples_por_sujeto=True,
                           normalizacion_version="pasaporte-v1"),
    DefinicionIdentificador(tipo="NIT", esquema="REGISTRO_FISCAL",
                           jurisdiccion_requerida=True, multiples_por_sujeto=False,
                           admite_digito_verificacion=True),
    DefinicionIdentificador(tipo="REGISTRO_EMPRESARIAL", esquema="REGISTRO_EMPRESARIAL",
                           jurisdiccion_requerida=True, multiples_por_sujeto=True),
)


class EquivalenciaCalidad(DTO):
    codigo_original: Codigo
    calidad: CalidadDato


class CatalogoCalidadFuente(DTO):
    fuente_codigo: Codigo
    version: Codigo
    equivalencias: tuple[EquivalenciaCalidad, ...]

    @model_validator(mode="after")
    def no_duplicar_calidades(self):
        codigos = [e.codigo_original for e in self.equivalencias]
        if len(codigos) != len(set(codigos)):
            raise ValueError("Calidad original duplicada")
        return self

    def resolver(self, codigo_original):
        return next((e.calidad for e in self.equivalencias if e.codigo_original == codigo_original),
                    CalidadDato.DESCONOCIDO)
