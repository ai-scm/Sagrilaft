"""Traduce el reporte de Tusdatos al contrato 2.0, solo con las fuentes SAGRILAFT aprobadas.

Reglas (decisiones del 2026-11-12 y comportamiento observado en el sandbox):

- Se lee el campo propio de cada fuente (`ofac`, `lista_onu`, `peps`…), no
  `dict_hallazgos`: allí no aparecen los aciertos de OFAC/ONU y en NIT viene nulo.
- Cada campo puede ser booleano, objeto, lista, texto o `"Error"`:
  objeto/lista con datos → candidato; `true` sin detalle → hallazgo sin estructura;
  `false`, vacío o nulo → sin registro; `"Error"` o código en `errores` → fuente fallida;
  campo ausente → fuente no disponible en el plan.
- `peps_internacionales`, `listas_restrictivas` y `listas_vinculantes` son categorías de
  los registros de `peps`/`peps_denom` (campo CATEGORIA), no campos propios.
- Todo lo demás del reporte (Sisben, RUAF, FOSYGA, etc.) se descarta antes de guardar.
- El nivel de riesgo de Tusdatos es configurable en su cuenta: se informa, no decide.
"""
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from domain.listas.contratos import (
    Advertencia, Candidato, Cobertura, Conclusion, Criterio, ErrorConsulta, Estado, Hallazgo,
    Implementacion, Motivo, ResultadoProveedorV2,
)

PROVEEDOR = "tusdatos"
ADAPTADOR_VERSION = "tusdatos-v1"
ALGORITMO_VERSION = "tusdatos-fuentes-v1"
PERSONA, EMPRESA = "PERSONA", "EMPRESA"
AMBOS = frozenset({PERSONA, EMPRESA})

# Tipos del expediente/criterio → tipo de Tusdatos. Alcance aprobado: CC, CE, pasaporte, NIT.
TIPOS_DOCUMENTO = {"CC": "CC", "CE": "CE", "NIT": "NIT", "PAS": "PP", "PASAPORTE": "PP", "PP": "PP"}


@dataclass(frozen=True)
class FuenteSagrilaft:
    codigo: str
    nombre: str
    campos: tuple[str, ...]
    errores: tuple[str, ...]
    aplica: frozenset = AMBOS
    por_nombre: bool = False
    # Si el campo no viene en el reporte, ¿la fuente impide concluir? Las fuentes que
    # Tusdatos solo incluye cuando hay registro (p. ej. PEP por función pública) no.
    ausencia_bloquea: bool = True


FUENTES = (
    FuenteSagrilaft("ofac", "OFAC (Lista Clinton), por documento", ("ofac",), ("ofac", "ofac_offline", "ofac_database_id")),
    FuenteSagrilaft("ofac_nombre", "OFAC (Lista Clinton), por nombre", ("ofac_nombre",),
                    ("ofac_nombre", "ofac_offline_name", "ofac_database_nombre"), frozenset({PERSONA}), True),
    # El catálogo de errores de Tusdatos usa dos códigos para ONU: lista_onu y onu.
    FuenteSagrilaft("lista_onu", "Consejo de Seguridad de la ONU", ("lista_onu",), ("lista_onu", "onu")),
    FuenteSagrilaft("interpol", "INTERPOL", ("interpol",), ("interpol",), frozenset({PERSONA})),
    FuenteSagrilaft("europol", "EUROPOL", ("europol",), ("europol",), frozenset({PERSONA})),
    FuenteSagrilaft("peps", "Listas y PEP, por documento", ("peps",), ("peps",)),
    FuenteSagrilaft("peps_denom", "Listas y PEP, por nombre", ("peps_denom",), ("peps_denom",), AMBOS, True),
    FuenteSagrilaft("cidob", "CIDOB, PEP a nivel mundial", ("cidob",), ("cidob",), frozenset({PERSONA}), True),
    # PEP por cargo en la función pública colombiana. En el sandbox solo aparece cuando hay
    # registro, así que su ausencia no impide concluir (por confirmar con datos reales).
    FuenteSagrilaft("peps_funcion_publica", "Listas y PEP, función pública (Colombia)", ("peps_funcion_publica",),
                    ("peps_funcion_publica",), frozenset({PERSONA}), ausencia_bloquea=False),
    FuenteSagrilaft("procuraduria", "Procuraduría General de la Nación", ("procuraduria",), ("procuraduria", "procuraduria_db")),
    FuenteSagrilaft("contraloria", "Contraloría General de la República", ("contraloria", "contraloria2"),
                    ("contraloria", "contraloria_db")),
    FuenteSagrilaft("policia", "Policía Nacional", ("policia",), ("policia",), frozenset({PERSONA})),
)
FUENTES_POR_CODIGO = {f.codigo: f for f in FUENTES}
CATEGORIAS_PEP = (("restrictiv", "listas_restrictivas"), ("vinculant", "listas_vinculantes"), ("internacional", "peps_internacionales"))
CAMPOS_APROBADOS = frozenset(c for f in FUENTES for c in f.campos)
CODIGOS_HALLAZGO_APROBADOS = CAMPOS_APROBADOS | {c for _, c in CATEGORIAS_PEP} | {
    f"{c}_denom" for _, c in CATEGORIAS_PEP}
# Texto con que la Policía informa ausencia de antecedentes (por verificar con datos reales).
_POLICIA_SIN_ANTECEDENTES = re.compile(r"no\s+tiene\s+asuntos\s+pendientes", re.IGNORECASE)
_NOMBRE = ("NOMBRECOMPLETO", "NOMBRE_PEP", "name", "nombre", "Nombre", "nombres", "nombre_completo", "title", "contador")
_UID = ("ID", "CODIGO", "id", "codigo")
_MAX_ATRIBUTOS, _MAX_TEXTO = 40, 500


@dataclass(frozen=True)
class SolicitudTusdatos:
    tipo_documento: str
    numero: str
    sujeto: str
    nombre: str | None = None
    fecha_expedicion: date | None = None

    @property
    def es_nit(self) -> bool:
        return self.tipo_documento == "NIT"


@dataclass(frozen=True)
class Interpretacion:
    resultado: ResultadoProveedorV2
    respuesta_filtrada: dict = field(default_factory=dict)


def traducir_criterio(criterio: Criterio) -> SolicitudTusdatos:
    """Tusdatos consulta por documento; el nombre solo se envía para pasaporte."""
    for identificador in criterio.identificadores:
        tipo = TIPOS_DOCUMENTO.get(identificador.tipo.upper())
        if tipo is None:
            continue
        if tipo == "PP" and not (criterio.nombre and len(criterio.nombre.strip()) >= 5):
            raise ValueError("Tusdatos exige el nombre completo para consultar un pasaporte")
        if tipo == "CE" and criterio.fecha_expedicion is None:
            raise ValueError("Tusdatos exige la fecha de expedición para consultar una cédula de extranjería")
        return SolicitudTusdatos(tipo_documento=tipo, numero=identificador.valor,
            sujeto=EMPRESA if tipo == "NIT" else PERSONA, nombre=criterio.nombre if tipo == "PP" else None,
            fecha_expedicion=criterio.fecha_expedicion if tipo == "CE" else None)
    raise ValueError("Tusdatos requiere una cédula (CC o CE), un pasaporte o un NIT")


def fuentes_para(sujeto: str) -> tuple[str, ...]:
    return tuple(f.codigo for f in FUENTES if sujeto in f.aplica)


def _id(consulta_id, *partes) -> uuid.UUID:
    return uuid.uuid5(consulta_id, "/".join(("tusdatos", *map(str, partes))))


def _texto(valor, limite=_MAX_TEXTO) -> str:
    if isinstance(valor, (dict, list)):
        valor = json.dumps(valor, ensure_ascii=False, sort_keys=True)
    texto = " ".join(str(valor).split())
    return texto[:limite]


def _vacio(valor) -> bool:
    if valor is None or valor is False or valor == "":
        return True
    if isinstance(valor, dict):
        return all(_vacio(v) or (isinstance(v, str) and not v.strip()) for v in valor.values())
    if isinstance(valor, list):
        return all(_vacio(v) for v in valor)
    return isinstance(valor, str) and not valor.strip()


def _atributos(registro: dict) -> dict:
    atributos = {}
    for clave, valor in registro.items():
        if len(atributos) >= _MAX_ATRIBUTOS:
            break
        clave = _texto(clave, 64).rstrip(":").strip()
        if clave and not _vacio(valor):
            atributos[clave] = _texto(valor)
    return atributos


def _nombre_registro(registro: dict, respaldo: str) -> str:
    for clave in _NOMBRE:
        if isinstance(registro.get(clave), str) and registro[clave].strip():
            return _texto(registro[clave])
    completo = " ".join(str(registro.get(c, "")).strip() for c in ("First Name:", "Last Name:")).strip()
    if completo:
        return _texto(completo)
    nombres = " ".join(str(registro.get(c, "")).strip() for c in ("PRIMER_NOMBRE", "SEGUNDO_NOMBRE", "PRIMER_APELLIDO", "SEGUNDO_APELLIDO")).strip()
    return _texto(nombres) if nombres else respaldo


def _uid(registro: dict) -> str | None:
    for clave in _UID:
        valor = registro.get(clave)
        if isinstance(valor, (str, int)) and str(valor).strip():
            return _texto(valor, 64)
    return None


def _categoria_pep(registro: dict) -> str | None:
    texto = " ".join(str(registro.get(c, "")) for c in ("CATEGORIA", "TIPO_LISTA", "ORIGEN_LISTA", "NOMBRE_LISTA")).casefold()
    return next((codigo for patron, codigo in CATEGORIAS_PEP if patron in texto), None)


def _registros(valor):
    """Normaliza el campo de una fuente: (registros estructurados, textos, hay_marca_sin_detalle)."""
    if valor is True:
        return [], [], True
    if isinstance(valor, dict):
        return ([valor] if not _vacio(valor) else []), [], False
    if isinstance(valor, list):
        registros = [v for v in valor if isinstance(v, dict) and not _vacio(v)]
        textos = [v for v in valor if isinstance(v, str) and v.strip()]
        return registros, textos, any(v is True for v in valor)
    if isinstance(valor, str) and valor.strip():
        return [], [valor], False
    return [], [], False


def interpretar_reporte(reporte: dict, *, consulta_id: uuid.UUID, solicitud: SolicitudTusdatos, criterio: Criterio,
                        errores_estado=(), fecha_inicio: datetime, fecha_fin: datetime,
                        fuentes: tuple[str, ...] | None = None, validado: bool | None = None) -> Interpretacion:
    """`fuentes`: las fijadas al admitir (manifiesto); por defecto, las aprobadas para el sujeto.
    `validado`: lo que Tusdatos informa al terminar (False = no pudo validar el documento)."""
    errores = set(errores_estado) | {e for e in (reporte.get("errores") or []) if isinstance(e, str)}
    tipo_sujeto = "ENTIDAD" if solicitud.sujeto == EMPRESA else "PERSONA"
    titular = reporte.get("nombre") if isinstance(reporte.get("nombre"), str) and reporte["nombre"].strip() else None
    cobertura, candidatos, hallazgos, advertencias = [], [], [], []
    codigos = fuentes or fuentes_para(solicitud.sujeto)
    if any(codigo not in FUENTES_POR_CODIGO for codigo in codigos):
        raise ValueError("Fuente fijada desconocida por este adaptador")
    for codigo in codigos:
        fuente = FUENTES_POR_CODIGO[codigo]
        cobertura_id = _id(consulta_id, "cobertura", codigo)
        valores = [(campo, reporte[campo]) for campo in fuente.campos if campo in reporte]
        base = dict(id=cobertura_id, fuente_codigo=codigo, nombre_origen=fuente.nombre, requerida=True)
        if not valores and not errores & set(fuente.errores):
            cobertura.append(Cobertura(**{**base, "requerida": fuente.ausencia_bloquea}, estado="NO_DISPONIBLE",
                                       motivo="La fuente no vino en el reporte" + ("" if fuente.ausencia_bloquea
                                              else "; Tusdatos solo la incluye cuando hay registro")))
            advertencias.append(Advertencia(codigo="FUENTE_NO_DISPONIBLE", descripcion=fuente.nombre, cobertura_id=cobertura_id))
            continue
        if errores & set(fuente.errores) or any(isinstance(v, str) and v.strip().casefold() == "error" for _, v in valores):
            cobertura.append(Cobertura(**base, estado="FALLIDA", motivo="Tusdatos informó error al consultar la fuente"))
            advertencias.append(Advertencia(codigo="FUENTE_FALLIDA", descripcion=fuente.nombre, cobertura_id=cobertura_id))
            continue
        cobertura.append(Cobertura(**base, estado="CONSULTADA"))
        consultado = (solicitud.nombre or criterio.nombre or "Nombre resuelto por el proveedor") if fuente.por_nombre \
            else f"{solicitud.tipo_documento} {solicitud.numero}"
        for campo, valor in valores:
            registros, textos, marca = _registros(valor)
            for indice, registro in enumerate(registros):
                nombre = _nombre_registro(registro, _texto(titular) if titular else f"Registro reportado en {fuente.nombre}")
                atributos = _atributos(registro)
                if codigo in {"peps", "peps_denom"} and (categoria := _categoria_pep(registro)):
                    atributos["categoria_sagrilaft"] = categoria
                candidatos.append(Candidato(id=_id(consulta_id, "candidato", campo, indice), cobertura_id=cobertura_id,
                    uid_origen=_uid(registro), tipo_sujeto=tipo_sujeto, nombre_principal=nombre, atributos=atributos,
                    motivos=(Motivo(campo=codigo, valor_consultado=_texto(consultado), valor_registro=nombre, metodo="PROVEEDOR"),),
                    algoritmo_version=ALGORITMO_VERSION))
            for indice, texto in enumerate(textos):
                if codigo == "policia" and _POLICIA_SIN_ANTECEDENTES.search(texto):
                    continue
                hallazgos.append(Hallazgo(id=_id(consulta_id, "texto", campo, indice), cobertura_id=cobertura_id,
                    codigo=codigo, descripcion=_texto(texto), referencia_raw=campo))
            if marca:
                hallazgos.append(Hallazgo(id=_id(consulta_id, "marca", campo), cobertura_id=cobertura_id, codigo=codigo,
                    descripcion=f"{fuente.nombre}: Tusdatos reporta un registro sin detalle; revisar el PDF del proveedor",
                    referencia_raw=campo))
    if validado is False:
        advertencias.append(Advertencia(codigo="DOCUMENTO_NO_VALIDADO", descripcion=(
            "Tusdatos no pudo validar el documento contra la fuente oficial. Las búsquedas por documento "
            "pueden no corresponder al titular: confirme el número y el tipo antes de dar por buena la ausencia de registros")))
    nivel = reporte.get("hallazgos")
    if isinstance(nivel, str) and nivel.strip():
        advertencias.append(Advertencia(codigo="NIVEL_INFORMADO_PROVEEDOR", descripcion=_texto(
            f"Nivel general informado por Tusdatos: {nivel.strip()}. Lo configura su cuenta; no es una decisión de cumplimiento")))
    no_aplicados = [Advertencia(codigo="CRITERIO_NO_APLICADO", descripcion=campo) for campo in
                    ("nombres_adicionales", "fecha_nacimiento", "nacionalidades", "ubicacion") if getattr(criterio, campo)]
    if criterio.nombre and solicitud.tipo_documento != "PP":
        no_aplicados.append(Advertencia(codigo="CRITERIO_NO_APLICADO",
            descripcion="nombre: Tusdatos consulta por documento y resuelve el nombre por su cuenta"))
    requeridas = [c for c in cobertura if c.requerida]
    if all(c.estado == "CONSULTADA" for c in requeridas):
        estado = Estado.COMPLETADA
        conclusion = Conclusion.CON_CANDIDATOS if candidatos or hallazgos else Conclusion.SIN_CANDIDATOS
    else:
        estado = Estado.PARCIAL if any(c.estado == "CONSULTADA" for c in requeridas) else Estado.FALLIDA
        conclusion = Conclusion.NO_CONCLUYENTE
    error = None
    if estado == Estado.FALLIDA:
        error = ErrorConsulta(codigo="FUENTES_NO_CONSULTADAS", mensaje="Tusdatos no pudo consultar las fuentes requeridas",
                              correlacion_id=consulta_id, reintentable=True)
    resultado = ResultadoProveedorV2(consulta_id=consulta_id, implementacion=Implementacion.EXTERNO, proveedor=PROVEEDOR,
        estado_ejecucion=estado, conclusion_busqueda=conclusion, cobertura=tuple(cobertura), candidatos=tuple(candidatos),
        hallazgos_no_estructurados=tuple(hallazgos), advertencias=tuple(advertencias), criterios_no_aplicados=tuple(no_aplicados),
        fecha_inicio=fecha_inicio, fecha_fin=max(fecha_fin, fecha_inicio), error=error)
    return Interpretacion(resultado=resultado, respuesta_filtrada=filtrar_reporte(reporte))


def filtrar_reporte(reporte: dict) -> dict:
    """Subconjunto que se guarda en PostgreSQL: solo fuentes aprobadas y metadatos del reporte."""
    hallazgos = {}
    for nivel, lista in (reporte.get("dict_hallazgos") or {}).items():
        if isinstance(lista, list):
            hallazgos[nivel] = [h for h in lista if isinstance(h, dict)
                                and (h.get("codigo") in CODIGOS_HALLAZGO_APROBADOS or h.get("fuente") in CAMPOS_APROBADOS)]
    return {"id": reporte.get("id"), "typedoc": reporte.get("typedoc"), "fecha": reporte.get("fecha"),
            "nombre": reporte.get("nombre"), "nivel": reporte.get("hallazgos"),
            "errores": sorted(e for e in (reporte.get("errores") or []) if e in {c for f in FUENTES for c in f.errores}),
            "fuentes": {campo: reporte[campo] for campo in sorted(CAMPOS_APROBADOS) if campo in reporte},
            "dict_hallazgos": hallazgos}


def resultado_sin_reporte(*, consulta_id: uuid.UUID, sujeto: str, codigo: str, mensaje: str, fecha_inicio: datetime,
                          fecha_fin: datetime, estado_cobertura="FALLIDA", advertencia: str | None = None) -> ResultadoProveedorV2:
    """Cierre con constancia cuando Tusdatos respondió pero no hay reporte (titular no autoriza, caché sin referencia)."""
    cobertura = tuple(Cobertura(id=_id(consulta_id, "cobertura", c), fuente_codigo=c, nombre_origen=FUENTES_POR_CODIGO[c].nombre,
                                estado=estado_cobertura, requerida=True, motivo=_texto(mensaje)) for c in fuentes_para(sujeto))
    return ResultadoProveedorV2(consulta_id=consulta_id, implementacion=Implementacion.EXTERNO, proveedor=PROVEEDOR,
        estado_ejecucion=Estado.FALLIDA, conclusion_busqueda=Conclusion.NO_CONCLUYENTE, cobertura=cobertura,
        advertencias=(Advertencia(codigo=codigo, descripcion=_texto(advertencia or mensaje)),),
        fecha_inicio=fecha_inicio, fecha_fin=max(fecha_fin, fecha_inicio),
        error=ErrorConsulta(codigo=codigo, mensaje=_texto(mensaje), correlacion_id=consulta_id, reintentable=False))
