"""Traduce el reporte de Tusdatos a su contrato propio (`tusdatos-1`), solo con las fuentes SAGRILAFT aprobadas.

Reglas (decisiones del 2026-11-12 y comportamiento observado en el sandbox):

- Se lee el campo propio de cada fuente (`ofac`, `lista_onu`, `peps`…), no
  `dict_hallazgos`: allí no aparecen los aciertos de OFAC/ONU y en NIT viene nulo.
- Cada campo puede ser booleano, objeto, lista, texto o `"Error"`:
  objeto/lista con datos → registro con su detalle completo; texto → registro con ese texto;
  `true` → registro sin detalle; `false`, vacío o nulo → sin registro;
  `"Error"` o código en `errores` → fuente no consultada; campo ausente → fuente no incluida.
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

from domain.listas.contratos import Conclusion, Criterio, ErrorConsulta, Estado
from domain.listas.contratos_tusdatos import (
    AvisoTusdatos, FuenteTusdatos, HallazgoInformado, RegistroTusdatos, ResultadoTusdatos,
)
from infrastructure.listas.tusdatos.catalogos import descripcion_hallazgo, nombre_fuente

PROVEEDOR = "tusdatos"
ADAPTADOR_VERSION = "tusdatos-v2"
ADAPTADORES_ANTERIORES = frozenset({"tusdatos-v1"})  # resultado en contrato 2.0
ALGORITMO_VERSION = "tusdatos-fuentes-v2"
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
    # Nombre del archivo de la captura de pantalla que Tusdatos publica para la fuente
    # (static.tusdatos.co/static/img/<dest>/<captura>.jpg). None: la fuente no genera captura.
    captura: str | None = None
    # False: Tusdatos no publica el modelo de la fuente; el detalle se guarda tal como llega.
    documentada: bool = True

    @property
    def codigos_estado(self) -> frozenset:
        """Códigos con que /api/v1/sources/status informa la fuente en línea (sin copias en base de datos)."""
        return frozenset(c for c in self.errores if not any(m in c for m in ("_db", "database", "offline")))


FUENTES = (
    FuenteSagrilaft("ofac", "OFAC (Lista Clinton), por documento", ("ofac",), ("ofac", "ofac_offline", "ofac_database_id"),
                    captura="ofac", documentada=False),
    FuenteSagrilaft("ofac_nombre", "OFAC (Lista Clinton), por nombre", ("ofac_nombre",),
                    ("ofac_nombre", "ofac_offline_name", "ofac_database_nombre"), frozenset({PERSONA}), True, captura="ofac_nombre", documentada=False),
    # El catálogo de errores de Tusdatos usa dos códigos para ONU: lista_onu y onu. La captura se llama onu.jpg.
    FuenteSagrilaft("lista_onu", "Consejo de Seguridad de la ONU", ("lista_onu",), ("lista_onu", "onu"), captura="onu", documentada=False),
    FuenteSagrilaft("interpol", "INTERPOL", ("interpol",), ("interpol",), frozenset({PERSONA}), captura="interpol", documentada=False),
    FuenteSagrilaft("europol", "EUROPOL", ("europol",), ("europol",), frozenset({PERSONA}), captura="europol", documentada=False),
    FuenteSagrilaft("peps", "Listas y PEP, por documento", ("peps",), ("peps",)),
    FuenteSagrilaft("peps_denom", "Listas y PEP, por nombre", ("peps_denom",), ("peps_denom",), AMBOS, True),
    FuenteSagrilaft("cidob", "CIDOB, PEP a nivel mundial", ("cidob",), ("cidob",), frozenset({PERSONA}), True, captura="cidob"),
    # PEP por cargo en la función pública colombiana. En el sandbox solo aparece cuando hay
    # registro, así que su ausencia no impide concluir (por confirmar con datos reales).
    FuenteSagrilaft("peps_funcion_publica", "Listas y PEP, función pública (Colombia)", ("peps_funcion_publica",),
                    ("peps_funcion_publica",), frozenset({PERSONA}), ausencia_bloquea=False, documentada=False),
    FuenteSagrilaft("procuraduria", "Procuraduría General de la Nación", ("procuraduria",), ("procuraduria", "procuraduria_db"),
                    captura="procuraduria"),
    FuenteSagrilaft("contraloria", "Contraloría General de la República", ("contraloria", "contraloria2"),
                    ("contraloria", "contraloria_db")),
    FuenteSagrilaft("policia", "Policía Nacional", ("policia",), ("policia",), frozenset({PERSONA}), captura="policia"),
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
_MAX_TEXTO = 500


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
    resultado: ResultadoTusdatos
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
        numero = identificador.valor.strip()
        if tipo == "NIT":
            # Tusdatos espera el NIT sin dígito de verificación: «900.123.456-7» → «900.123.456».
            numero = re.sub(r"\s*-\s*\d$", "", numero)
        return SolicitudTusdatos(tipo_documento=tipo, numero=numero,
            sujeto=EMPRESA if tipo == "NIT" else PERSONA, nombre=criterio.nombre if tipo == "PP" else None,
            # CE: obligatoria. CC: opcional; con ella Tusdatos valida la fecha y consulta fuentes adicionales.
            fecha_expedicion=criterio.fecha_expedicion if tipo in ("CC", "CE") else None)
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


# Tamaño máximo del detalle de un registro (JSON). Un registro mayor se guarda parcial y se avisa.
_MAX_DETALLE = 32_000
_NIVELES = {"altos": "alto", "medios": "medio", "bajos": "bajo", "infos": "informativo"}


def _detalle(registro: dict) -> tuple[dict, bool]:
    """El registro tal como llega (sin aplanar ni recortar textos); parcial solo si es desmedido."""
    if len(json.dumps(registro, ensure_ascii=False, default=str)) <= _MAX_DETALLE:
        return registro, False
    parcial, tamano = {}, 2
    for clave, valor in registro.items():
        tamano += len(json.dumps({clave: valor}, ensure_ascii=False, default=str))
        if tamano > _MAX_DETALLE:
            break
        parcial[clave] = valor
    return parcial, True


def _fuente_de_hallazgo(codigo: str, codigos: tuple[str, ...]) -> str | None:
    """Fuente aprobada a la que pertenece un código de hallazgo (prefijo más largo; categorías de PEP)."""
    for patron, categoria in CATEGORIAS_PEP:
        if codigo == f"{categoria}_denom":
            return "peps_denom" if "peps_denom" in codigos else None
        if codigo == categoria:
            return "peps" if "peps" in codigos else None
    alias = {"ofac_offline": "ofac", "ofac_offline_name": "ofac_nombre", "onu": "lista_onu"}
    if codigo in alias:
        return alias[codigo] if alias[codigo] in codigos else None
    candidatas = [c for c in codigos if codigo == c or codigo.startswith(f"{c}_")]
    return max(candidatas, key=len) if candidatas else None


def _hallazgos_por_fuente(reporte: dict, codigos: tuple[str, ...]) -> dict[str, list[HallazgoInformado]]:
    por_fuente: dict[str, list[HallazgoInformado]] = {}
    for nivel, lista in (reporte.get("dict_hallazgos") or {}).items():
        for entrada in lista if isinstance(lista, list) else ():
            codigo = entrada.get("codigo") if isinstance(entrada, dict) else None
            fuente = _fuente_de_hallazgo(codigo, codigos) if isinstance(codigo, str) and codigo.strip() else None
            if fuente is None:
                continue
            texto = descripcion_hallazgo(codigo) or entrada.get("hallazgo") or codigo
            por_fuente.setdefault(fuente, []).append(HallazgoInformado(codigo=_texto(codigo, 64),
                descripcion=_texto(texto, 2000), nivel=_NIVELES.get(nivel, _texto(nivel, 64))))
    return por_fuente


def _registros_de_campo(consulta_id, campo: str, valor, fuente: FuenteSagrilaft, titular: str | None) -> list[RegistroTusdatos]:
    estructurados, textos, marca = _registros(valor)
    registros = []
    for indice, registro in enumerate(estructurados):
        detalle, recortado = _detalle(registro)
        categoria = _categoria_pep(registro) if fuente.codigo in {"peps", "peps_denom"} else None
        registros.append(RegistroTusdatos(id=_id(consulta_id, "registro", campo, indice), campo=campo,
            titulo=_nombre_registro(registro, _texto(titular) if titular else f"Registro reportado en {fuente.nombre}"),
            identificador_origen=_uid(registro), categoria=categoria, detalle=detalle, detalle_recortado=recortado))
    for indice, texto in enumerate(textos):
        if fuente.codigo == "policia" and _POLICIA_SIN_ANTECEDENTES.search(texto):
            continue
        registros.append(RegistroTusdatos(id=_id(consulta_id, "texto", campo, indice), campo=campo,
            titulo=_texto(texto), detalle={"texto": texto[:_MAX_DETALLE]}, detalle_recortado=len(texto) > _MAX_DETALLE))
    if marca:
        registros.append(RegistroTusdatos(id=_id(consulta_id, "marca", campo), campo=campo, sin_detalle=True,
            titulo=f"{fuente.nombre}: registro informado sin detalle"))
    return registros


def interpretar_reporte(reporte: dict, *, consulta_id: uuid.UUID, solicitud: SolicitudTusdatos, criterio: Criterio,
                        errores_estado=(), fecha_inicio: datetime, fecha_fin: datetime,
                        fuentes: tuple[str, ...] | None = None, validado: bool | None = None,
                        fuentes_caidas: frozenset[str] = frozenset(),
                        recuperacion: str | None = None, reporte_id: str | None = None,
                        huella_respuesta: str | None = None) -> Interpretacion:
    """`fuentes`: las fijadas al admitir (manifiesto); por defecto, las aprobadas para el sujeto.
    `validado`: lo que Tusdatos informa al terminar (False = no pudo validar el documento).
    `fuentes_caidas`: códigos que Tusdatos reportaba caídos o en mantenimiento al cerrar.
    `recuperacion`: texto que explica que es la recarga automática de una consulta anterior.
    `reporte_id` y `huella_respuesta`: id del reporte en Tusdatos y SHA-256 del JSON completo recibido."""
    errores = set(errores_estado) | {e for e in (reporte.get("errores") or []) if isinstance(e, str)}
    titular = reporte.get("nombre") if isinstance(reporte.get("nombre"), str) and reporte["nombre"].strip() else None
    codigos = tuple(fuentes or fuentes_para(solicitud.sujeto))
    if any(codigo not in FUENTES_POR_CODIGO for codigo in codigos):
        raise ValueError("Fuente fijada desconocida por este adaptador")
    hallazgos = _hallazgos_por_fuente(reporte, codigos)
    version_peps = reporte.get("peps_version") if isinstance(reporte.get("peps_version"), str) else None
    consolidado = tuple(r for r in reporte.get("peps_consolidado") or () if isinstance(r, dict)) \
        if isinstance(reporte.get("peps_consolidado"), list) else ()
    resultado_fuentes = []
    for codigo in codigos:
        fuente = FUENTES_POR_CODIGO[codigo]
        valores = [(campo, reporte[campo]) for campo in fuente.campos if campo in reporte]
        base = dict(id=_id(consulta_id, "cobertura", codigo), codigo=codigo,
                    nombre=_texto(nombre_fuente(codigo) or fuente.nombre), estructura_documentada=fuente.documentada,
                    hallazgos=tuple(hallazgos.get(codigo, ())))
        if codigo in {"peps", "peps_denom"}:
            base.update(version_base=_texto(version_peps, 64) if version_peps and version_peps.strip() else None,
                        resumen=consolidado if codigo == "peps" else ())
        if errores & set(fuente.errores) or any(isinstance(v, str) and v.strip().casefold() == "error" for _, v in valores):
            motivo = ("Tusdatos informa la fuente caída o en mantenimiento; no se pudo consultar" if codigo in fuentes_caidas
                      else "Tusdatos informó error al consultar la fuente")
            resultado_fuentes.append(FuenteTusdatos(**base, estado="NO_CONSULTADA", motivo=motivo))
            continue
        if not valores:
            resultado_fuentes.append(FuenteTusdatos(**base, estado="NO_INCLUIDA", requerida=fuente.ausencia_bloquea,
                motivo="La fuente no vino en el reporte" + ("" if fuente.ausencia_bloquea
                       else "; Tusdatos solo la incluye cuando hay registro")))
            continue
        registros = [r for campo, valor in valores for r in _registros_de_campo(consulta_id, campo, valor, fuente, titular)]
        resultado_fuentes.append(FuenteTusdatos(**base, estado="CON_REGISTRO" if registros else "SIN_REGISTRO",
                                                registros=tuple(registros)))
    avisos = []
    if validado is False:
        avisos.append(AvisoTusdatos(codigo="DOCUMENTO_NO_VALIDADO", descripcion=(
            "Tusdatos no pudo validar el documento contra la fuente oficial. Las búsquedas por documento "
            "pueden no corresponder al titular: confirme el número y el tipo antes de dar por buena la ausencia de registros")))
    if recuperacion:
        avisos.append(AvisoTusdatos(codigo="RECUPERACION_AUTOMATICA", descripcion=_texto(recuperacion, 2000)))
    requeridas = [f for f in resultado_fuentes if f.requerida]
    con_registro = any(f.registros for f in resultado_fuentes)
    if all(f.estado in {"CON_REGISTRO", "SIN_REGISTRO"} for f in requeridas):
        estado = Estado.COMPLETADA
        conclusion = Conclusion.CON_CANDIDATOS if con_registro else Conclusion.SIN_CANDIDATOS
    else:
        estado = Estado.PARCIAL if any(f.estado in {"CON_REGISTRO", "SIN_REGISTRO"} for f in requeridas) else Estado.FALLIDA
        conclusion = Conclusion.NO_CONCLUYENTE
    error = None
    if estado == Estado.FALLIDA:
        error = ErrorConsulta(codigo="FUENTES_NO_CONSULTADAS", mensaje="Tusdatos no pudo consultar las fuentes requeridas",
                              correlacion_id=consulta_id, reintentable=True)
    nivel = reporte.get("hallazgos")
    resultado = ResultadoTusdatos(consulta_id=consulta_id, proveedor=PROVEEDOR, estado_ejecucion=estado,
        conclusion_busqueda=conclusion, titular_nombre=_texto(titular) if titular else None, documento_validado=validado,
        nivel_informado_proveedor=_texto(nivel, 64) if isinstance(nivel, str) and nivel.strip() else None,
        fuentes=tuple(resultado_fuentes), avisos=tuple(avisos), reporte_proveedor_id=reporte_id,
        huella_respuesta=huella_respuesta, fecha_inicio=fecha_inicio, fecha_fin=max(fecha_fin, fecha_inicio), error=error)
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
            "dest": reporte.get("dest") if isinstance(reporte.get("dest"), str) else None,  # ruta de las capturas
            "errores": sorted(e for e in (reporte.get("errores") or []) if e in {c for f in FUENTES for c in f.errores}),
            "fuentes": {campo: reporte[campo] for campo in sorted(CAMPOS_APROBADOS) if campo in reporte},
            "dict_hallazgos": hallazgos}


def resultado_sin_reporte(*, consulta_id: uuid.UUID, sujeto: str, codigo: str, mensaje: str, fecha_inicio: datetime,
                          fecha_fin: datetime, advertencia: str | None = None) -> ResultadoTusdatos:
    """Cierre con constancia cuando no hay reporte (titular no autoriza, documento no encontrado, fuentes caídas…)."""
    fuentes = tuple(FuenteTusdatos(id=_id(consulta_id, "cobertura", c), codigo=c,
                                   nombre=_texto(nombre_fuente(c) or FUENTES_POR_CODIGO[c].nombre),
                                   estado="NO_CONSULTADA", motivo=_texto(mensaje, 2000),
                                   estructura_documentada=FUENTES_POR_CODIGO[c].documentada) for c in fuentes_para(sujeto))
    return ResultadoTusdatos(consulta_id=consulta_id, proveedor=PROVEEDOR, estado_ejecucion=Estado.FALLIDA,
        conclusion_busqueda=Conclusion.NO_CONCLUYENTE, fuentes=fuentes,
        avisos=(AvisoTusdatos(codigo=codigo, descripcion=_texto(advertencia, 2000)),) if advertencia else (),
        fecha_inicio=fecha_inicio, fecha_fin=max(fecha_fin, fecha_inicio),
        error=ErrorConsulta(codigo=codigo, mensaje=_texto(mensaje), correlacion_id=consulta_id, reintentable=False))
