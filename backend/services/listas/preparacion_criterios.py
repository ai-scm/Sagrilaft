"""Prepara criterios desde una copia explícita del expediente; sin ORM, red o búsqueda."""
from datetime import date
import re
from typing import Annotated, Literal

from pydantic import Field

from domain.listas.catalogos_busqueda import CatalogoPreparacion, PAISES_ISO_3166_1_ALPHA_2
from domain.listas.contratos import Codigo, DTO
from domain.listas.contratos_busqueda import CriterioBusqueda, IdentificadorConsulta
from domain.listas.datos_busqueda import Huella, TextoDato, UbicacionContexto

FechaDeclarada = Annotated[date, Field(strict=True)] | str


class DatosExpedienteBusqueda(DTO):
    expediente_id: Codigo
    tipo_persona: str | None = None
    tipo_contraparte: str | None = None
    razon_social: str | None = None
    tipo_identificacion: str | None = None
    numero_identificacion: str | None = None
    digito_verificacion: str | None = None
    direccion: str | None = None
    ciudad: str | None = None
    pais: str | None = None
    nombre_representante: str | None = None
    tipo_doc_representante: str | None = None
    numero_doc_representante: str | None = None
    fecha_nacimiento: FechaDeclarada | None = None
    fecha_expedicion: FechaDeclarada | None = None
    ciudad_nacimiento: str | None = None
    ciudad_expedicion: str | None = None
    nacionalidad: str | None = None
    direccion_residencia: str | None = None
    ciudad_residencia: str | None = None
    direccion_funciones: str | None = None
    ciudad_funciones: str | None = None
    pais_funciones: str | None = None


class OrigenCriterio(DTO):
    campo_criterio: TextoDato
    campo_expediente: Codigo
    valor_original: TextoDato


class AvisoPreparacion(DTO):
    codigo: Codigo
    campo_expediente: Codigo


class SujetoPreparado(DTO):
    rol: Literal["CONTRAPARTE", "REPRESENTANTE"]
    criterio: CriterioBusqueda
    origenes: tuple[OrigenCriterio, ...]
    avisos: tuple[AvisoPreparacion, ...]
    criterios_exigidos_no_interpretados: tuple[Codigo, ...] = ()


class SujetoOmitido(DTO):
    rol: Literal["CONTRAPARTE", "REPRESENTANTE"]
    motivo: Codigo
    origenes: tuple[OrigenCriterio, ...] = ()
    avisos: tuple[AvisoPreparacion, ...] = ()


class PreparacionExpediente(DTO):
    expediente_id: Codigo
    catalogo_version: Codigo
    catalogo_huella: Huella
    sujetos: tuple[SujetoPreparado, ...]
    omitidos: tuple[SujetoOmitido, ...]


class _PreparadorSujeto:
    def __init__(self, datos, catalogo):
        self.datos = datos
        self.catalogo = catalogo
        self.origenes = []
        self.avisos = []
        self.exigidos_no_interpretados = set()

    def valor(self, campo, destino):
        valor = getattr(self.datos, campo)
        if valor is None or isinstance(valor, str) and not valor.strip():
            return None
        self.origenes.append(OrigenCriterio(campo_criterio=destino, campo_expediente=campo,
                                            valor_original=valor.isoformat() if isinstance(valor, date) else valor))
        return valor

    def avisar(self, codigo, campo):
        self.avisos.append(AvisoPreparacion(codigo=codigo, campo_expediente=campo))

    def pais(self, campo, destino):
        """Los selectores del formulario ya guardan el código ISO 3166-1 de dos letras
        (mismo paquete que usa OFAC); se valida y se usa directamente, sin asumir
        Colombia ni ningún otro país por defecto. Un canal futuro con texto libre
        ("Colombia" en vez de "CO") seguiría resolviéndose por el catálogo declarado."""
        valor = self.valor(campo, destino)
        if valor is None:
            return None
        codigo = valor.strip().upper()
        if codigo not in PAISES_ISO_3166_1_ALPHA_2:
            codigo = self.catalogo.pais(valor)
        if codigo is None:
            self.avisar("PAIS_NO_INTERPRETADO", campo)
        return codigo

    def fecha(self, campo):
        valor = self.valor(campo, campo)
        if valor is None or type(valor) is date:
            return valor
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
                raise ValueError("Formato de fecha no completo")
            return date.fromisoformat(valor)
        except ValueError:
            self.avisar("FECHA_NO_INTERPRETADA", campo)
            return None

    def documento(self, campo_tipo, campo_valor, campo_digito=None, pais_emisor=None):
        tipo = self.valor(campo_tipo, "identificadores.tipo")
        valor = self.valor(campo_valor, "identificadores.valor")
        if valor is None:
            return None
        if tipo is None:
            self.avisar("TIPO_DOCUMENTO_AUSENTE", campo_tipo)
            self.exigidos_no_interpretados.add("identificadores")
            return None
        definicion = self.catalogo.identificador(tipo)
        if definicion is None:
            self.avisar("TIPO_DOCUMENTO_NO_INTERPRETADO", campo_tipo)
            self.exigidos_no_interpretados.add("identificadores")
            # Conservar tipo/valor para que el evaluador no oculte un criterio exigido.
            return IdentificadorConsulta(tipo=tipo, valor=valor)
        digito = None
        if campo_digito and definicion.admite_digito_verificacion:
            digito = self.valor(campo_digito, "identificadores.digito_verificacion")
            if digito is not None and not re.fullmatch(r"[0-9]", digito):
                self.avisar("DIGITO_NO_INTERPRETADO", campo_digito)
                self.exigidos_no_interpretados.add("identificadores")
                digito = None
        return IdentificadorConsulta(tipo=definicion.tipo, esquema=definicion.esquema,
                                     valor=valor, digito_verificacion=digito, pais_emisor=pais_emisor)

    def ubicacion(self, rol, campo_texto, campo_ciudad, campo_pais=None):
        textos = [self.valor(campo, "ubicaciones") for campo in (campo_texto, campo_ciudad) if campo]
        pais = self.pais(campo_pais, "ubicaciones.pais") if campo_pais else None
        texto = ", ".join(t for t in textos if t)
        return UbicacionContexto(rol=rol, texto=texto or None, pais=pais) if texto or pais else None

    def preparar(self, rol, tipo, bloque_personal=False, natural=False):
        self.valor("tipo_persona", "tipo_sujeto" if rol == "CONTRAPARTE"
                   else "contexto.tipo_persona_contraparte")
        self.valor("tipo_contraparte", "contexto.rol_comercial")
        principal = self.valor("nombre_representante" if bloque_personal else "razon_social", "nombre")
        adicional = None
        documentos = []
        # País emisor declarado para cada documento, nunca asumido cuando no está declarado:
        # - el NIT o registro empresarial de una contraparte jurídica usa su país de domicilio,
        #   porque una empresa no se registra con un NIT de un país distinto al suyo;
        # - el documento de identificación de una persona natural (sea la propia contraparte
        #   o el representante legal) usa su nacionalidad declarada, no su domicilio ni el
        #   lugar donde ejerce funciones, que no equivalen al país que expide su documento.
        pais_domicilio = self.pais("pais", "identificadores.pais_emisor") if rol == "CONTRAPARTE" and not natural else None
        pais_persona = self.pais("nacionalidad", "identificadores.pais_emisor") if bloque_personal else None
        if natural:
            adicional = self.valor("razon_social", "nombres_adicionales" if principal else "nombre")
            if principal is None:
                principal, adicional = adicional, None
            documentos.append(self.documento("tipo_identificacion", "numero_identificacion",
                "digito_verificacion", pais_emisor=pais_persona))
        if bloque_personal:
            documentos.append(self.documento("tipo_doc_representante", "numero_doc_representante",
                pais_emisor=pais_persona))
        elif not natural:
            documentos.append(self.documento("tipo_identificacion", "numero_identificacion",
                "digito_verificacion", pais_emisor=pais_domicilio))
        # No duplicar un documento repetido; conservar procedencia de ambos campos.
        documentos = list(dict.fromkeys(d for d in documentos if d is not None))
        if not principal and not documentos:
            return SujetoOmitido(rol=rol, motivo=("CRITERIO_PRIMARIO_NO_INTERPRETADO"
                if self.exigidos_no_interpretados else "SIN_CRITERIO_PRIMARIO"),
                origenes=tuple(self.origenes), avisos=tuple(self.avisos))
        nacimiento = expedicion = None
        nacionalidad = None
        ubicaciones = []
        if bloque_personal:
            nacimiento, expedicion = self.fecha("fecha_nacimiento"), self.fecha("fecha_expedicion")
            nacionalidad = self.pais("nacionalidad", "nacionalidades")
            for rol_dato, campo in (("NACIMIENTO", "ciudad_nacimiento"), ("EMISION", "ciudad_expedicion")):
                texto = self.valor(campo, "ubicaciones")
                if texto:
                    ubicaciones.append(UbicacionContexto(rol=rol_dato, texto=texto))
            ubicacion = self.ubicacion("FUNCIONES", "direccion_funciones", "ciudad_funciones", "pais_funciones")
            if ubicacion:
                ubicaciones.append(ubicacion)
        if natural:
            ubicacion = self.ubicacion("RESIDENCIA", "direccion_residencia", "ciudad_residencia")
            if ubicacion:
                ubicaciones.append(ubicacion)
        if rol == "CONTRAPARTE":
            ubicacion = self.ubicacion("DOMICILIO", "direccion", "ciudad", "pais")
            if ubicacion:
                ubicaciones.append(ubicacion)
        if tipo == "NO_DETERMINADO":
            self.avisar("NATURALEZA_NO_DETERMINADA", "tipo_persona")
        exigidos = tuple(c for c, presente in (("nombre", bool(principal)), ("identificadores", bool(documentos))) if presente)
        criterio = CriterioBusqueda(tipo_sujeto=tipo, nombre=principal,
            nombres_adicionales=(adicional,) if adicional and adicional != principal else (),
            identificadores=tuple(documentos), fecha_nacimiento=nacimiento, fecha_expedicion=expedicion,
            nacionalidades=(nacionalidad,) if nacionalidad else (), ubicaciones=tuple(ubicaciones),
            campos_exigidos=exigidos)
        return SujetoPreparado(rol=rol, criterio=criterio, origenes=tuple(self.origenes),
            avisos=tuple(self.avisos), criterios_exigidos_no_interpretados=tuple(sorted(self.exigidos_no_interpretados)))


def preparar_expediente(datos: DatosExpedienteBusqueda, catalogo: CatalogoPreparacion) -> PreparacionExpediente:
    """El bloque del paso 3 es de la propia contraparte cuando tipo_persona es natural."""
    naturaleza = (datos.tipo_persona or "").strip().casefold()
    natural = naturaleza == "natural"
    juridica = naturaleza in {"juridica", "jurídica"}
    tipo = "PERSONA" if natural else "ENTIDAD" if juridica else "NO_DETERMINADO"
    sujetos, omitidos = [], []
    contraparte = _PreparadorSujeto(datos, catalogo).preparar(
        "CONTRAPARTE", tipo, bloque_personal=natural, natural=natural)
    if isinstance(contraparte, SujetoPreparado):
        sujetos.append(contraparte)
    else:
        omitidos.append(contraparte)
    if juridica:
        representante = _PreparadorSujeto(datos, catalogo).preparar("REPRESENTANTE", "PERSONA", bloque_personal=True)
        if isinstance(representante, SujetoPreparado):
            sujetos.append(representante)
        else:
            omitidos.append(representante)
    else:
        omitidos.append(SujetoOmitido(rol="REPRESENTANTE", motivo=(
            "BLOQUE_PERSONAL_ES_CONTRAPARTE" if natural else "NATURALEZA_NO_DETERMINADA")))
    return PreparacionExpediente(expediente_id=datos.expediente_id, catalogo_version=catalogo.version,
        catalogo_huella=catalogo.huella, sujetos=tuple(sujetos), omitidos=tuple(omitidos))
