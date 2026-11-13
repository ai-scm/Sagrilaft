"""Motor local común. Recibe hechos ya fijados; no accede a SQL ni decide cumplimiento."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from uuid import UUID, uuid5

from domain.listas.catalogos_busqueda import CatalogoPreparacion, IDENTIFICADORES_INICIALES
from domain.listas.comparacion_hechos import contraste_fecha, misma_identidad, motivo
from domain.listas.comparacion_identificadores import clave_documento, mismo_esquema, preparar_identificador
from domain.listas.comparacion_nombres import comparar_nombre, partes_nombre
from domain.listas.contratos import DTO
from domain.listas.contratos_busqueda import CandidatoClasificado, CriterioBusqueda
from domain.listas.datos_busqueda import HechoFecha, HechoTexto, HechoUbicacion, RegistroBusqueda

VERSION_REGLAS = "clasificacion-f63-v1"


def _fecha_original_legible(original):
    """Normaliza el campo original de FechaDato para presentación humana.

    Los registros importados antes de la corrección almacenan el nodo
    DatePeriod completo como JSON.  Esta función extrae Year/Month/Day
    y devuelve una fecha legible; los registros nuevos (ya legibles)
    pasan sin cambio.
    """
    if not original or not original.startswith("{"):
        return original
    try:
        nodo = json.loads(original)
    except (json.JSONDecodeError, TypeError):
        return original
    if not isinstance(nodo, dict) or nodo.get("etiqueta") != "DatePeriod":
        return original
    puntos = []
    for borde in nodo.get("hijos", []):
        if borde.get("etiqueta") not in ("Start", "End"):
            continue
        for punto in borde.get("hijos", []):
            if punto.get("etiqueta") not in ("From", "To"):
                continue
            componentes = {h["etiqueta"]: h.get("texto", "") for h in punto.get("hijos", [])}
            anio = componentes.get("Year", "")
            if not anio:
                continue
            partes = [anio.zfill(4)]
            mes = componentes.get("Month", "")
            if mes:
                partes.append(mes.zfill(2))
                dia = componentes.get("Day", "")
                if dia:
                    partes.append(dia.zfill(2))
            puntos.append("-".join(partes))
    aproximada = any(
        b.get("atributos", {}).get("Approximate") in ("true", "1")
        for b in nodo.get("hijos", []) if b.get("etiqueta") in ("Start", "End"))
    prefijo = "~" if aproximada else ""
    if not puntos:
        return original
    unicos = list(dict.fromkeys(puntos))
    if len(unicos) == 1:
        return f"{prefijo}{unicos[0]}"
    return f"{prefijo}{unicos[0]} a {unicos[-1]}"
VERSION_ALGORITMO = "recuperacion-f63-v1"
CATALOGO_MOTOR = CatalogoPreparacion(version="motor-f63-v1", identificadores=tuple(
    d.model_copy(update={"normalizacion_version": "nit-co-v1"}) if d.tipo == "NIT" else d
    for d in IDENTIFICADORES_INICIALES))


class CriterioNoUtilizable(ValueError):
    pass


@dataclass(frozen=True)
class ParametrosMotor:
    maximo_registros: int = 50000
    maximo_candidatos: int = 1000
    maximo_partes_nombre: int = 40
    genericos: tuple[str, ...] = ("juan", "maria", "jose", "empresa", "comercial", "servicios", "cliente", "proveedor")

    def __post_init__(self):
        if min(self.maximo_registros, self.maximo_candidatos, self.maximo_partes_nombre) < 1:
            raise ValueError("Los límites del motor deben ser positivos")

    @property
    def huella(self):
        return sha256(json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class EvaluacionBusqueda(DTO):
    candidatos: tuple[CandidatoClasificado, ...]
    concluyente: bool
    advertencias: tuple[str, ...]
    campos_no_aplicados: tuple[str, ...]
    registros_evaluados: int
    registros_disponibles: int
    candidatos_recuperados: int
    fecha_referencia: date
    reglas_version: str = VERSION_REGLAS
    algoritmo_version: str = VERSION_ALGORITMO
    parametros_huella: str
    catalogo_huella: str


@dataclass(frozen=True)
class CoincidenciaNominal:
    nombre: object
    completo: bool


@dataclass(frozen=True)
class CoincidenciaDocumental:
    dato: object
    fuerte: bool
    cuestionada: bool
    conflicto_digito: bool


def clave_registro(registro):
    r = registro.referencia
    return (r.fuente_codigo, r.version_id, r.registro_id, r.respuesta_sha256,
            r.campo_original if r.registro_id is None else None)


def nacimiento_consultado(criterio, registro, ancla):
    hechos = [h for h in registro.hechos if isinstance(h, HechoFecha) and h.campo == "fecha_nacimiento"
              and misma_identidad(ancla, h, registro)]
    comparaciones = [contraste_fecha(criterio.fecha_nacimiento, h) for h in hechos]
    compatibles = any(r in {"COINCIDE", "COMPATIBLE"} for r, _ in comparaciones)
    coincide_fuerte = any(r == "COINCIDE" and f for r, f in comparaciones)
    contradice = not compatibles and any(r == "DIFERENTE" and f for r, f in comparaciones)
    return coincide_fuerte, contradice


class MotorBusqueda:
    def __init__(self, catalogo=CATALOGO_MOTOR, parametros=ParametrosMotor()):
        self.catalogo = catalogo
        self.parametros = parametros

    def evaluar(self, criterio: CriterioBusqueda, registros: tuple[RegistroBusqueda, ...],
                consulta_id: UUID, coberturas: dict[str, UUID], fecha_referencia: date):
        """El llamador debe entregar la representación completa, íntegra y fijada de F6.2."""
        if type(fecha_referencia) is not date:
            raise ValueError("La evaluación necesita una fecha de referencia explícita")
        nombres_utiles, documentos, no_aplicados = self.validar_criterio(criterio)
        self._validar_corpus(registros, coberturas)
        advertencias = set()
        completa = len(registros) <= self.parametros.maximo_registros
        if not completa:
            advertencias.add("LIMITE_REGISTROS_NO_CONCLUYENTE")
        ambiguedades = self._documentos_ambiguos(registros) if completa else set()
        tipos_fuente = set()
        candidatos = []
        for registro in registros[:self.parametros.maximo_registros]:
            if criterio.identificadores and any(preparar_identificador(d, self.catalogo, fuente=True) is None
                                               for d in registro.identificadores):
                no_aplicados.add("identificadores")
            tipos_fuente.update(d.tipo for d in registro.identificadores)
            nombres_completos = all(len(partes_nombre(n.valor)) <= self.parametros.maximo_partes_nombre for n in registro.nombres)
            if not nombres_completos:
                advertencias.add("NOMBRE_FUENTE_SUPERA_LIMITE")
            candidato = self._evaluar_registro(criterio, nombres_utiles, documentos, registro,
                consulta_id, coberturas[registro.referencia.fuente_codigo], fecha_referencia, ambiguedades, completa and nombres_completos)
            if candidato:
                candidatos.append(candidato)
                no_aplicados.update(m.campo for m in candidato.motivos
                    if m.metodo == "FECHA_NO_INTERPRETABLE")
        # No se inventa una comparación: si ningún registro cargado puede tener este tipo
        # de documento (p. ej. cédula colombiana contra OFAC), se declara sin equivalente.
        if completa and any(uno is not None and uno.tipo not in tipos_fuente for _, uno in documentos):
            no_aplicados.add("identificadores")
        prioridad = {"ALTA": 0, "MEDIA": 1, "BAJA": 2}
        candidatos.sort(key=lambda c: (prioridad[c.nivel], str(c.id)))
        recuperados = len(candidatos)
        if recuperados > self.parametros.maximo_candidatos:
            advertencias.add("LIMITE_CANDIDATOS_NO_CONCLUYENTE")
            candidatos = candidatos[:self.parametros.maximo_candidatos]
        exigidos = set(criterio.campos_exigidos)
        if not nombres_utiles:
            exigidos.add("identificadores")
        if exigidos & no_aplicados:
            advertencias.add("CRITERIO_EXIGIDO_NO_APLICADO")
        return EvaluacionBusqueda(candidatos=candidatos,
            concluyente=not advertencias, advertencias=sorted(advertencias),
            campos_no_aplicados=sorted(no_aplicados), registros_evaluados=min(len(registros), self.parametros.maximo_registros),
            registros_disponibles=len(registros), parametros_huella=self.parametros.huella,
            catalogo_huella=self.catalogo.huella, candidatos_recuperados=recuperados,
            fecha_referencia=fecha_referencia)

    def validar_criterio(self, criterio):
        """La admisión valida sin fabricar una evaluación ni una cobertura ficticia."""
        nombres = tuple(n for n in (criterio.nombre, *criterio.nombres_adicionales) if n)
        nombres_utiles = tuple(n for n in nombres if self._nombre_util(n))
        documentos = tuple((d, preparar_identificador(d, self.catalogo)) for d in criterio.identificadores)
        no_aplicados = set()
        if criterio.nombre and not self._nombre_util(criterio.nombre):
            no_aplicados.add("nombre")
        if any(not self._nombre_util(n) for n in criterio.nombres_adicionales):
            no_aplicados.add("nombres_adicionales")
        if any(d is None for _, d in documentos):
            no_aplicados.add("identificadores")
        if not nombres_utiles and not any(d is not None for _, d in documentos):
            raise CriterioNoUtilizable("Se necesita un nombre distintivo o identificador con esquema conocido")
        return nombres_utiles, documentos, no_aplicados

    def _nombre_util(self, nombre):
        partes = partes_nombre(nombre)
        return bool(partes) and len(partes) <= self.parametros.maximo_partes_nombre and not all(
            p in self.parametros.genericos or len(p) == 1 for p in partes)

    @staticmethod
    def _validar_corpus(registros, coberturas):
        if not coberturas:
            raise ValueError("Se requiere cobertura de al menos una fuente")
        if len(set(coberturas.values())) != len(coberturas):
            raise ValueError("Cada fuente necesita su propia cobertura")
        claves, versiones = set(), defaultdict(set)
        for registro in registros:
            clave = clave_registro(registro)
            if clave in claves:
                raise ValueError("Registro duplicado en la representación entregada")
            claves.add(clave)
            r = registro.referencia
            versiones[r.fuente_codigo].add(r.version_id)
            if r.fuente_codigo not in coberturas:
                raise ValueError("Falta cobertura fijada de una fuente")
        if any(len(v) > 1 for v in versiones.values()):
            raise ValueError("El motor no mezcla versiones de una misma fuente")

    def _documentos_ambiguos(self, registros):
        asignaciones = defaultdict(set)
        for registro in registros:
            for dato in registro.identificadores:
                preparado = preparar_identificador(dato, self.catalogo, fuente=True)
                if preparado and dato.calidad != "FALSO":
                    clave = (registro.referencia.fuente_codigo, registro.referencia.version_id, clave_documento(preparado))
                    asignaciones[clave].add(clave_registro(registro))
        return {clave for clave, sujetos in asignaciones.items() if len(sujetos) > 1}

    def _nombres(self, criterio, consultados, registro, motivos):
        coincidencias = []
        for consultado in consultados:
            for nombre in registro.nombres:
                if len(partes_nombre(nombre.valor)) > self.parametros.maximo_partes_nombre:
                    continue
                comparacion = comparar_nombre(consultado, nombre.valor, self.parametros.genericos,
                    admitir_iniciales=criterio.tipo_sujeto != "ENTIDAD")
                if not comparacion:
                    continue
                cuestionado = nombre.calidad == "FALSO"
                motivos.append(motivo("nombre", "COMPATIBLE", comparacion.metodo,
                    "Coincide una variante nominal; no confirma identidad."
                    + (" El alias es débil." if nombre.alias_debil else "")
                    + (" La fuente cuestiona este nombre." if cuestionado else ""),
                    consultado, nombre.valor, nombre))
                coincidencias.append(CoincidenciaNominal(nombre, comparacion.completo and not nombre.alias_debil and not cuestionado))
        return coincidencias

    def _identificadores(self, documentos, registro, motivos, ambiguedades, completa):
        coincidencias, contradicciones = [], []
        for consultado, uno in documentos:
            if uno is None:
                motivos.append(motivo("identificadores", "NO_APLICADO", "ESQUEMA_NO_SOPORTADO",
                    "El identificador consultado no tiene una interpretación utilizable.", consultado.valor))
                continue
            for dato in registro.identificadores:
                otro = preparar_identificador(dato, self.catalogo, fuente=True)
                if otro is None or not mismo_esquema(uno, otro):
                    continue
                misma_jurisdiccion = uno.pais is not None and uno.pais == otro.pais
                if uno.valor != otro.valor:
                    motivos.append(motivo("identificadores", "DIFERENTE", "DOCUMENTO_EXACTO",
                        "Los valores completos del mismo esquema son diferentes.", consultado.valor, dato.valor, dato))
                    if (misma_jurisdiccion and not uno.definicion.multiples_por_sujeto and dato.calidad != "FALSO"):
                        contradicciones.append(dato)
                    continue
                conflicto_digito = uno.digito is not None and otro.digito is not None and uno.digito != otro.digito
                ambigua = (registro.referencia.fuente_codigo, registro.referencia.version_id, clave_documento(otro)) in ambiguedades
                jurisdiccion = misma_jurisdiccion or not uno.definicion.jurisdiccion_requerida
                # El dígito de verificación solo tiene un esquema implementado para Colombia
                # (nit-co-v1); exigirlo para el NIT de otro país no sería una regla de ese
                # país, sería inventar un control que no existe para su formato.
                control = (not uno.definicion.admite_digito_verificacion or uno.pais != "CO"
                           or (uno.digito is not None and uno.digito == otro.digito))
                # OFAC no certifica la identidad de un documento (no existe esa señal en su
                # esquema): solo declara si el número es válido o fraudulento (ValidityID).
                # "Confirmado" se exige donde la fuente sí lo certifica (nombres, fechas);
                # para documentos, el estándar que la fuente realmente ofrece es "no fraudulento".
                fuerte = (dato.calidad != "FALSO" and otro.esquema_explicito and jurisdiccion and control
                          and not ambigua and completa and misma_identidad(dato, dato, registro))
                metodo = "DOCUMENTO_EXACTO" if uno.definicion.normalizacion_version == "conservacion-v1" else uno.definicion.normalizacion_version.upper().replace("-", "_")
                motivos.append(motivo("identificadores", "COMPATIBLE" if conflicto_digito or not jurisdiccion else "COINCIDE", metodo,
                    "Coincide la base, pero los dígitos de verificación difieren." if conflicto_digito else
                    "Coincide el valor completo del identificador; se verifican esquema, jurisdicción y calidad por separado.",
                    consultado.valor, dato.valor, dato))
                if uno.pais and otro.pais and uno.pais != otro.pais:
                    motivos.append(motivo("pais_emisor", "DIFERENTE", "JURISDICCION_DOCUMENTAL",
                        "El número coincide, pero los países emisores declarados son distintos.", uno.pais, otro.pais, dato))
                for condicion, metodo, explicacion in (
                    (not jurisdiccion, "JURISDICCION_NO_CORROBORADA", "Falta jurisdicción compatible; no sustenta ALTA."),
                    (ambigua, "DOCUMENTO_AMBIGUO", "El identificador está asignado a varios registros de la misma fuente."),
                    (dato.calidad == "FALSO", "CALIDAD_INSUFICIENTE", "La fuente declara este documento como fraudulento."),
                    (not control and not conflicto_digito, "CONTROL_FISCAL_INCOMPLETO", "No se verificó el dígito fiscal completo."),
                    (not otro.esquema_explicito, "ESQUEMA_FUENTE_AUSENTE", "La fuente no declaró un esquema verificable.")):
                    if condicion:
                        motivos.append(motivo("identificadores", "NO_APLICADO", metodo, explicacion,
                                              consultado.valor, dato.valor, dato))
                coincidencias.append(CoincidenciaDocumental(dato, fuerte, dato.calidad == "FALSO", conflicto_digito))
        return coincidencias, contradicciones

    @staticmethod
    def _contexto(criterio, registro, motivos):
        for campo in ("fecha_nacimiento", "fecha_expedicion"):
            consultada = getattr(criterio, campo)
            hechos = [h for h in registro.hechos if isinstance(h, HechoFecha) and h.campo == campo]
            if consultada is None:
                continue
            if not hechos:
                motivos.append(motivo(campo, "AUSENTE", "SIN_DATO_FUENTE", "La fuente no aporta este dato.", consultada.isoformat()))
            for hecho in hechos:
                resultado, _ = contraste_fecha(consultada, hecho)
                metodo = "FECHA_NO_INTERPRETABLE" if hecho.valor.precision == "NO_INTERPRETADA" else "PRECISION_Y_CALIDAD_FECHA"
                motivos.append(motivo(campo, resultado, metodo,
                    "La comparación respeta precisión, alternativas, calendario y fiabilidad.",
                    consultada.isoformat(), _fecha_original_legible(hecho.valor.original), hecho))
        for campo, valores in (("nacionalidad", criterio.nacionalidades), ("ciudadania", criterio.ciudadanias)):
            for valor in valores:
                hechos = [h for h in registro.hechos if isinstance(h, HechoTexto) and h.campo == campo]
                if not hechos:
                    motivos.append(motivo(campo, "AUSENTE", "SIN_DATO_FUENTE", "La fuente no aporta este contexto.", valor))
                for hecho in hechos:
                    resultado = "NO_APLICADO" if hecho.calidad == "FALSO" else "COINCIDE" if valor == hecho.valor else "DIFERENTE"
                    motivos.append(motivo(campo, resultado, "CONTEXTO_SIN_EXCLUSION", "Este contexto no confirma ni excluye identidad por sí solo.", valor, hecho.valor, hecho))
        ubicaciones = list(criterio.ubicaciones)
        if criterio.ubicacion and (criterio.ubicacion.texto or criterio.ubicacion.pais):
            from domain.listas.datos_busqueda import UbicacionContexto
            ubicaciones.append(UbicacionContexto(rol="OTRO", texto=criterio.ubicacion.texto, pais=criterio.ubicacion.pais))
        for ubicacion in ubicaciones:
            hechos = [h for h in registro.hechos if isinstance(h, HechoUbicacion) and h.valor.rol == ubicacion.rol]
            if not hechos:
                motivos.append(motivo("ubicaciones", "AUSENTE", "ROL_NO_DISPONIBLE", "No hay ubicación publicada con ese rol.", ubicacion.texto or ubicacion.pais))
            for hecho in hechos:
                for componente in ("pais", "texto"):
                    uno, otro = getattr(ubicacion, componente), getattr(hecho.valor, componente)
                    if uno is None:
                        continue
                    resultado = "AUSENTE" if otro is None else "NO_APLICADO" if hecho.calidad == "FALSO" else "COMPATIBLE" if uno == otro else "DIFERENTE"
                    motivos.append(motivo("ubicaciones", resultado, "ROL_GEOGRAFICO_" + componente.upper(),
                        "Se compara " + componente + " del rol " + ubicacion.rol
                        + (" histórico" if hecho.valor.historica else "") + "; no determina identidad.", uno, otro, hecho))

    @staticmethod
    def _nombre_contradictorio(consultados, registro, ancla, genericos=()):
        for nombre in registro.nombres:
            if nombre.alias_debil and nombre.calidad != "FALSO" and misma_identidad(ancla, nombre, registro):
                if any((c := comparar_nombre(consultado, nombre.valor, genericos)) and c.metodo in {"NOMBRE_NORMALIZADO", "ORDEN_DE_PARTES"}
                       for consultado in consultados):
                    # Un apodo publicado no se interpreta como afirmación de otro nombre civil.
                    return False
        solidos = [n for n in registro.nombres if not n.alias_debil and n.calidad != "FALSO"
                   and len(partes_nombre(n.valor)) >= 2 and misma_identidad(ancla, n, registro)]
        completos = [n for n in consultados if len(partes_nombre(n)) >= 2]
        return bool(solidos and completos) and not any(comparar_nombre(c, n.valor, genericos)
                                                      for c in completos for n in solidos)

    def _evaluar_registro(self, criterio, nombres, documentos, registro, consulta_id, cobertura_id,
                         fecha_referencia, ambiguedades, completa):
        motivos = []
        nominales = self._nombres(criterio, nombres, registro, motivos)
        documentales, distintos = self._identificadores(documentos, registro, motivos, ambiguedades, completa)
        if not nominales and not documentales:
            return None
        if (criterio.tipo_sujeto != "NO_DETERMINADO" and registro.tipo_sujeto != "NO_DETERMINADO"
                and criterio.tipo_sujeto != registro.tipo_sujeto and not documentales):
            return None
        self._contexto(criterio, registro, motivos)
        tipo_compatible = criterio.tipo_sujeto == registro.tipo_sujeto and criterio.tipo_sujeto != "NO_DETERMINADO"
        tipo_contradice = criterio.tipo_sujeto != "NO_DETERMINADO" and registro.tipo_sujeto != "NO_DETERMINADO" and not tipo_compatible
        anclas = [n.nombre for n in nominales] + [d.dato for d in documentales]
        conflicto_unico = any(d.vigencia and d.vigencia.calidad == "CONFIRMADO"
            and d.vigencia.desde <= fecha_referencia <= d.vigencia.hasta
            and any(misma_identidad(a, d, registro) for a in anclas) for d in distintos)
        fuertes = [d for d in documentales if d.fuerte and (criterio.tipo_sujeto != "ENTIDAD"
            or d.dato.esquema in {"REGISTRO_FISCAL", "REGISTRO_EMPRESARIAL"})]
        vinculacion_documental = not nombres or all(any(misma_identidad(d.dato, n, registro)
            for n in registro.nombres if not n.alias_debil and n.calidad != "FALSO") for d in fuertes)
        anclas_fecha = [d.dato for d in fuertes] or [n.nombre for n in nominales if n.completo] or anclas
        conflictos_fecha = [nacimiento_consultado(criterio, registro, a)[1] for a in anclas_fecha] if criterio.fecha_nacimiento else []
        conflicto_fecha = bool(conflictos_fecha) and (any(conflictos_fecha) if fuertes else all(conflictos_fecha))
        conflicto_nombre = any(self._nombre_contradictorio(nombres, registro, d.dato, self.parametros.genericos) for d in fuertes)
        conflicto = tipo_contradice or conflicto_fecha or conflicto_unico or conflicto_nombre
        fiscal = any(d.conflicto_digito and not d.cuestionada for d in documentales)
        nominal_solida = any(n.completo for n in nominales)
        nacimiento_fuerte = criterio.tipo_sujeto == "PERSONA" and criterio.fecha_nacimiento is not None and any(
            n.completo and len(partes_nombre(n.nombre.valor)) >= 2 and nacimiento_consultado(criterio, registro, n.nombre)[0]
            for n in nominales)
        if fiscal or fuertes and conflicto:
            nivel, regla = "MEDIA", "IDENTIFICADOR_CON_CONFLICTO"
            explicacion = "Existe coincidencia documental y una contradicción que requiere revisión prioritaria."
        elif conflicto:
            nivel, regla = "BAJA", "COINCIDENCIA_CONTRADICHA"
            explicacion = "Se recuperó una posible coincidencia, pero los datos de identidad presentan una contradicción."
        elif tipo_compatible and completa and vinculacion_documental and (fuertes or nacimiento_fuerte):
            nivel, regla = "ALTA", "DOCUMENTO_FUERTE" if fuertes else "NOMBRE_Y_NACIMIENTO_FUERTES"
            explicacion = "Coincide un identificador fuerte y no hay contradicción fuerte." if fuertes else "Coinciden un nombre completo y el nacimiento exacto confirmado de la misma identidad."
        elif nominal_solida or any(not d.cuestionada for d in documentales):
            nivel, regla = "MEDIA", "COINCIDENCIA_SIN_CORROBORACION"
            explicacion = "Hay una coincidencia utilizable, pero falta corroboración suficiente para ALTA."
        else:
            nivel, regla = "BAJA", "COINCIDENCIA_DEBIL"
            explicacion = "La coincidencia se apoya en un nombre parcial, alias débil o dato cuestionado."
        for condicion, campo, metodo, explicacion_motivo in (
            (tipo_contradice, "tipo_sujeto", "TIPO_INCOMPATIBLE", "La fuente y la consulta describen naturalezas de sujeto distintas."),
            (conflicto_fecha, "fecha_nacimiento", "NACIMIENTO_INCOMPATIBLE", "Las alternativas comparables de nacimiento de la identidad recuperada son incompatibles con la consulta."),
            (conflicto_unico, "identificadores", "IDENTIFICADOR_UNICO_INCOMPATIBLE", "Difiere un identificador único confirmado del mismo esquema y jurisdicción, con vigencia confirmada para la fecha de referencia."),
            (conflicto_nombre, "nombre", "NOMBRE_COMPLETO_INCOMPATIBLE", "El documento fuerte coincide, pero los nombres completos de esa identidad son incompatibles con el nombre consultado.")):
            if condicion:
                motivos.append(motivo(campo, "NO_APLICADO", metodo, explicacion_motivo))
        if nominal_solida and criterio.fecha_nacimiento and not nacimiento_fuerte and any(
                isinstance(h, HechoFecha) and h.campo == "fecha_nacimiento" and contraste_fecha(criterio.fecha_nacimiento, h)[0] == "COINCIDE"
                for h in registro.hechos):
            motivos.append(motivo("fecha_nacimiento", "NO_APLICADO", "VINCULACION_NO_CORROBORADA",
                "El nacimiento coincidente no puede combinarse con el nombre recuperado sin una vinculación de identidad compatible."))
        if not tipo_compatible:
            motivos.append(motivo("tipo_sujeto", "NO_APLICADO", "TIPO_NO_CORROBORADO", "La naturaleza del sujeto no permite una clasificación ALTA."))
        if not vinculacion_documental:
            motivos.append(motivo("nombre", "NO_APLICADO", "VINCULACION_DOCUMENTAL_AUSENTE", "No hay nombres sólidos vinculados a la identidad del documento para contrastar el nombre consultado."))
        nombre = next((n.valor for n in registro.nombres if n.tipo == "PRINCIPAL"), registro.nombres[0].valor)
        return CandidatoClasificado(id=uuid5(consulta_id, repr(clave_registro(registro))), cobertura_id=cobertura_id,
            registro_id=registro.referencia.registro_id, tipo_sujeto=registro.tipo_sujeto,
            nombre_principal=nombre, nivel=nivel, regla_codigo=regla, regla_version=VERSION_REGLAS,
            explicacion=explicacion, motivos=motivos, revision_prioritaria=bool(conflicto or fiscal),
            hechos=registro.hechos, nombres=registro.nombres, identificadores=registro.identificadores,
            relaciones=registro.relaciones, algoritmo_version=VERSION_ALGORITMO)
