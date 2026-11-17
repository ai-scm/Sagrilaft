"""Modalidad externa (Tusdatos): admisión por documento y protocolo por etapas en el trabajador.

Cada pasada del trabajador avanza una etapa y libera la consulta hasta el próximo intento:

    POR_LANZAR ──(turno de 5 s)──► LANZANDO ──► ESPERANDO ──► DESCARGANDO_PDF ──► TERMINADA
                                     │             │ (sondeo; una recarga gratuita
                                     │             │  si fallaron fuentes requeridas,
                                     │             │  esperando a que vuelvan si están caídas)
                                     └─ si el trabajador cae aquí, la consulta queda
                                        INDETERMINADA y nunca se relanza sola.

- LANZANDO se confirma en la base ANTES de llamar a `launch`, que gasta un crédito.
- El plazo es de 15 minutos desde la admisión; vencido, se cierra NO_CONCLUYENTE.
- Antes de lanzar, un NIT o una cédula de extranjería se valida con `verify/nit` o
  `verify/ce` (una sola vez por consulta). Si no existe, se cierra sin consultar listas;
  si no está vigente, se consulta igual y el resultado lleva un aviso.
- Si Tusdatos responde sin jobid (CC en su caché de 6 h), el reporte se busca en el
  historial de la cuenta (`/api/v1/checks`) y se sigue desde ahí sin gastar crédito.
- El PDF del proveedor se intenta dentro del mismo plazo; si no llega, la consulta se
  cierra igual y queda un evento PDF_PROVEEDOR_NO_DISPONIBLE (el id del reporte queda
  guardado para descargarlo después).
- En la misma etapa se guardan las capturas de pantalla por fuente que Tusdatos publica
  (OFAC, ONU, INTERPOL, Procuraduría…). Son gratis y no detienen el cierre.

Después del cierre (`revisar_pendientes`, cada minuto, sin gastar créditos):

- Si una consulta cerró con fuentes fallidas, se vuelve a recargar con `/api/retry` cuando
  esas fuentes estén operativas: 10 min, 1 h y 4 h después de cada cierre, como máximo tres
  veces y dentro de las 24 h. Cada recarga es una consulta nueva enlazada a la anterior
  (`consulta_previa_id`): el resultado cerrado no se toca. Si el usuario ya volvió a
  consultar ese documento en el expediente, no se recarga.
- Si el PDF o las capturas no llegaron antes del cierre, se vuelven a pedir en esos mismos
  tiempos y se suman como evidencia a la misma consulta.
"""
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from domain.listas.puertos import ListasNoDisponibles
from services.listas.modalidad_base import Admision, crear_grupo_por_documento, datos_sujeto


def _documento(criterio) -> tuple[str, str] | None:
    """(tipo Tusdatos, número sin separadores) del primer documento consultable del criterio."""
    from infrastructure.listas.tusdatos.adaptador import TIPOS_DOCUMENTO
    from infrastructure.listas.tusdatos.cliente import limpiar_documento
    for identificador in (criterio or {}).get("identificadores") or ():
        tipo = TIPOS_DOCUMENTO.get(str(identificador.get("tipo", "")).upper())
        if tipo:
            return tipo, limpiar_documento(identificador.get("valor", "")).upper()
    return None


def _aviso_no_vigente(progreso) -> str | None:
    """Texto del aviso al revisor si la verificación previa encontró el documento no vigente."""
    verificacion = getattr(progreso, "verificacion_documento", None) or {}
    if verificacion.get("resultado") != "NO_VIGENTE":
        return None
    que = "La empresa" if verificacion.get("tipo") == "NIT" else "La cédula de extranjería"
    estado = verificacion.get("estado") or "; ".join(verificacion.get("avisos") or ()) or "no vigente"
    return (f"{que} no figura vigente en la fuente oficial (estado informado: {estado}). "
            "Las listas se consultaron igual; confirme el documento con la contraparte")


def _aviso_recuperacion(consulta) -> str | None:
    """Texto del aviso al revisor si la consulta es la recarga automática de otra."""
    recupera = (consulta.manifiesto or {}).get("recupera") or {}
    if not recupera:
        return None
    return (f"Recarga automática de la consulta {recupera.get('consulta_id')} (intento {recupera.get('intento')} "
            f"de {len(ESPERAS_RECUPERACION)}): Tusdatos volvió a consultar las fuentes que habían fallado. "
            "No se gastó crédito")


def bloquear_documento(sesion, expediente_id, documento) -> None:
    """Serializa admisiones del mismo documento en el expediente hasta el fin de la transacción."""
    from sqlalchemy import text
    from services.listas.informes import calcular_huella
    clave = calcular_huella(["tusdatos-reutilizacion", expediente_id, *documento])
    sesion.execute(text("SELECT pg_advisory_xact_lock(:clave)"), {"clave": int(clave[:15], 16)})


def consulta_reutilizable(sesion, expediente_id, documento, ahora):
    """Consulta externa reciente del mismo documento en el expediente, en curso o con resultado usable."""
    from sqlalchemy import select
    from infrastructure.listas.tusdatos.adaptador import PROVEEDOR
    from infrastructure.persistencia.modelos_listas import ConsultaLista
    filas = sesion.execute(select(ConsultaLista.id, ConsultaLista.criterio_original).where(
        ConsultaLista.expediente_id == expediente_id, ConsultaLista.implementacion == "externo",
        ConsultaLista.proveedor == PROVEEDOR, ConsultaLista.estado.in_(ESTADOS_REUTILIZABLES),
        ConsultaLista.creado_en >= ahora - VENTANA_REUTILIZACION,
    ).order_by(ConsultaLista.creado_en.desc(), ConsultaLista.id.desc()))
    return next((fila.id for fila in filas if _documento(fila.criterio_original) == documento), None)

PLAZO = timedelta(minutes=15)
INTERVALO_LANZAMIENTOS = 5.0   # Tusdatos exige 5 s entre lanzamientos.
ESPERA_TRAS_LANZAR = 15.0      # Una consulta tarda en promedio un minuto.
ESPERA_SONDEO = 5.0            # Frecuencia de sondeo recomendada por Tusdatos.
ESPERA_RED = 15.0
CONCESION_PASADA = 300         # Cubre la llamada más lenta (PDF) con sus reintentos.
VIGENCIA_SALUD = 60.0          # Segundos que se reutiliza el estado de fuentes y créditos.
ESPERA_FUENTE_CAIDA = 60.0     # Cada cuánto se revisa si volvió una fuente caída antes de recargar.
VIGENCIA_SALUD_RECARGA = 10.0  # Para decidir la recarga se usa un estado reciente, no el de antes de lanzar.
MARGEN_RECARGA = timedelta(minutes=3)  # Tiempo mínimo antes del plazo para esperar y aun recargar.
VENTANA_CACHE = timedelta(hours=6)     # Tusdatos reutiliza una CC consultada en las últimas 6 h.
VENTANA_RECUPERACION = timedelta(hours=24)  # Después no se recupera nada: el revisor ya decidió con lo que había.
ESPERAS_RECUPERACION = (timedelta(minutes=10), timedelta(hours=1), timedelta(hours=4))
TIPOS_VERIFICABLES = frozenset({"NIT", "CE"})  # verify/nit (cámaras de comercio) y verify/ce (Migración)
ESTADOS_CAIDOS = frozenset({"under_maintenance", "source_down"})
MENSAJES_NO_ENCONTRADO = {
    "NIT": "Tusdatos no encontró el NIT en el registro mercantil (RUES). Envíe el NIT sin dígito de verificación",
    "CE": "Tusdatos no encontró la cédula de extranjería en el registro de Migración Colombia",
    "CC": "Tusdatos no encontró el documento en la fuente oficial",
    "PP": "Tusdatos no encontró el pasaporte",
}
registro = logging.getLogger(__name__)
# «Bloquear y reutilizar»: dentro del mismo expediente, una consulta del mismo documento de
# las últimas 6 horas se reutiliza en vez de gastar otro crédito. Solo dentro del expediente:
# reutilizar la de otro expediente expondría su resultado a quien no tiene acceso a él.
VENTANA_REUTILIZACION = timedelta(hours=6)
ESTADOS_REUTILIZABLES = ("PENDIENTE", "EN_CURSO", "COMPLETADA", "PARCIAL")


@dataclass(frozen=True)
class ConsultaCerrada:
    """Lo necesario para recuperar, después del cierre, lo que una consulta no alcanzó a traer."""
    id: object
    estado: str
    expediente_id: str | None
    creado_en: object
    finalizada_en: object
    criterio: dict
    manifiesto: dict
    resultado: dict | None
    reporte_id: str
    dest: str | None
    evidencias: frozenset
    eventos: frozenset


class ModalidadExterna:
    implementacion = "externo"
    version_contrato = "2.0"
    admite_forzar = True

    def __init__(self, fabrica_cliente=None, monotonic=time.monotonic):
        # Las pruebas inyectan un cliente con transporte simulado; en ejecución se arma desde el entorno.
        self._fabrica = fabrica_cliente
        self._monotonic = monotonic  # reloj de la caché de estado de fuentes y créditos
        self._clientes = {}
        self._salud = {}  # entorno → (instante, {código: estado} | None)
        self._sin_estado_avisado = set()  # entornos donde ya se registraron las fuentes sin estado

    # ── Configuración ────────────────────────────────────────────────────────

    @staticmethod
    def _configuracion(entorno):
        from infrastructure.listas.tusdatos.configuracion import ConfiguracionTusdatos
        return ConfiguracionTusdatos.desde_entorno(entorno)

    def cliente(self, entorno):
        if entorno not in self._clientes:
            if self._fabrica is not None:
                self._clientes[entorno] = self._fabrica(entorno)
            else:
                from infrastructure.listas.tusdatos.cliente import ClienteTusdatos
                self._clientes[entorno] = ClienteTusdatos(self._configuracion(entorno))
        return self._clientes[entorno]

    def disponible(self, entorno):
        if self._fabrica is not None:
            return True
        try:
            self._configuracion(entorno)
            return True
        except ListasNoDisponibles:
            return False

    def _ambiente(self, entorno):
        if self._fabrica is not None:
            return "pruebas"
        return "sandbox" if self._configuracion(entorno).es_sandbox else "produccion"

    def manifiesto(self, entorno, sujeto: str, forzar: bool = False) -> dict:
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION, ALGORITMO_VERSION, PROVEEDOR, fuentes_para
        return {"implementacion": self.implementacion, "proveedor": PROVEEDOR, "adaptador": ADAPTADOR_VERSION,
                "algoritmo": ALGORITMO_VERSION, "ambiente": self._ambiente(entorno),
                "fuentes": list(fuentes_para(sujeto)), "forzar": bool(forzar)}

    # ── Admisión ─────────────────────────────────────────────────────────────

    def recuperar_reintento(self, servicio, solicitud, clave):
        # El repositorio resuelve el reintento 2.0 dentro de la misma admisión.
        return None

    def crear(self, servicio, solicitud, clave, forzar: bool = False):
        from sqlalchemy import select
        from domain.listas.contratos import SolicitudIdempotente
        from infrastructure.listas.tusdatos.adaptador import PROVEEDOR, traducir_criterio
        from infrastructure.persistencia.modelos_listas import ConsultaLista
        traducida = traducir_criterio(solicitud.criterio)  # ValueError → 422, sin gastar créditos
        contexto = solicitud.contexto
        documento = _documento(solicitud.criterio.model_dump(mode="json"))
        peticion = SolicitudIdempotente(clave=clave, solicitud=solicitud)
        with servicio.sesiones.begin() as sesion:
            bloquear_documento(sesion, contexto.expediente_id, documento)
            # Un reintento con la misma clave lo resuelve la admisión (misma consulta o conflicto),
            # no la reutilización: así no se informa como reutilizada la propia consulta.
            propia = sesion.scalar(select(ConsultaLista.id).where(ConsultaLista.actor_emisor == servicio.actor.issuer,
                ConsultaLista.actor_sujeto == servicio.actor.sub, ConsultaLista.clave_idempotencia == clave,
                ConsultaLista.ambito_idempotencia == f"expediente:{contexto.expediente_id}:{contexto.sujeto_rol}"))
            if not forzar and propia is None:
                anterior = consulta_reutilizable(sesion, contexto.expediente_id, documento, servicio.repositorio.reloj())
                if anterior:
                    return Admision(anterior, reutilizada=True)
            identificador = servicio.repositorio.admitir(servicio.actor, peticion, PROVEEDOR,
                self.manifiesto(servicio.entorno, traducida.sujeto, forzar=forzar), sesion_actual=sesion)
        return Admision(identificador)

    def crear_grupo(self, servicio, expediente_id, clave, sesion):
        from domain.listas.contratos import Criterio
        from infrastructure.listas.tusdatos.adaptador import PROVEEDOR, TIPOS_DOCUMENTO, traducir_criterio

        def criterio_para(rol, expediente):
            nombre, tipo, documento = datos_sujeto(rol, expediente)
            tipo = (tipo or "").strip().upper()
            if not (documento and str(documento).strip()) or tipo not in TIPOS_DOCUMENTO:
                return None, "Tusdatos requiere un documento CC, CE, pasaporte o NIT"
            criterio = {"tipo_sujeto": "NO_DETERMINADO" if rol == "CONTRAPARTE" else "PERSONA",
                        "identificadores": [{"tipo": tipo, "valor": str(documento).strip()}]}
            if nombre and nombre.strip():
                criterio["nombre"] = nombre.strip()
            # La fecha de expedición guardada es la del documento de la contraparte.
            if rol == "CONTRAPARTE" and TIPOS_DOCUMENTO[tipo] == "CE" and getattr(expediente, "fecha_expedicion", None):
                criterio["fecha_expedicion"] = expediente.fecha_expedicion.isoformat()
            try:
                traducir_criterio(Criterio.model_validate(criterio))
            except ValueError as error:
                return None, str(error).split("\n")[0]
            return criterio, ""

        def manifiesto_para(criterio):
            return self.manifiesto(servicio.entorno, traducir_criterio(Criterio.model_validate(criterio)).sujeto)

        def reutilizable(criterio, sesion_grupo):
            documento = _documento(criterio)
            bloquear_documento(sesion_grupo, expediente_id, documento)
            return consulta_reutilizable(sesion_grupo, expediente_id, documento, servicio.repositorio.reloj())

        return crear_grupo_por_documento(servicio, expediente_id, clave, sesion, proveedor=PROVEEDOR,
                                         criterio_para=criterio_para, manifiesto_para=manifiesto_para,
                                         reutilizable=reutilizable)

    # ── Ejecución ────────────────────────────────────────────────────────────

    def reconoce(self, consulta):
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION
        return consulta.implementacion == self.implementacion and consulta.manifiesto.get("adaptador") == ADAPTADOR_VERSION

    def ejecutar(self, trabajador, concesion, consulta):
        from domain.listas.contratos import Criterio
        from infrastructure.listas.tusdatos.adaptador import traducir_criterio
        repositorio = trabajador.repositorio
        repositorio.renovar(concesion, CONCESION_PASADA)
        try:
            criterio = Criterio.model_validate(consulta.criterio)
            solicitud = traducir_criterio(criterio)
        except ValueError:
            return self._terminar_con_fallo(repositorio, concesion, "DATOS_ADMITIDOS_NO_INTERPRETABLES")
        if consulta.tiene_borrador:
            return self._cerrar(trabajador, concesion, consulta, solicitud)
        progreso = repositorio.progreso_externo(consulta.id)
        if progreso is None:
            repositorio.guardar_progreso(concesion, etapa="POR_LANZAR", vence_en=consulta.admitida_en + PLAZO,
                                         **self._verificacion_heredada(repositorio, consulta))
            progreso = repositorio.progreso_externo(consulta.id)
        if progreso.etapa == "TERMINADA":
            return repositorio.fallar(concesion, "EJECUCION_INTERRUMPIDA")
        if repositorio.reloj() >= progreso.vence_en:
            if progreso.etapa == "POR_LANZAR":
                return self._terminar_con_fallo(repositorio, concesion, "TIEMPO_AGOTADO_SIN_LANZAR")
            return self._terminar_con_fallo(repositorio, concesion, "TIEMPO_AGOTADO_PROVEEDOR", indeterminada=True)
        if progreso.etapa == "POR_LANZAR":
            if consulta.manifiesto.get("recupera"):
                return self._recargar_previa(trabajador, concesion, consulta, solicitud)
            return self._lanzar(trabajador, concesion, consulta, solicitud)
        if progreso.etapa == "ESPERANDO":
            return self._esperar(trabajador, concesion, consulta, criterio, solicitud, progreso)
        # LANZANDO sin borrador no debería llegar aquí: `reclamar` ya la deja indeterminada.
        return repositorio.fallar(concesion, "EFECTO_EXTERNO_DESCONOCIDO", indeterminada=True)

    def _lanzar(self, trabajador, concesion, consulta, solicitud):
        from infrastructure.listas.tusdatos.adaptador import PROVEEDOR, resultado_sin_reporte
        from infrastructure.listas.tusdatos.errores import (
            AccesoDenegado, CredencialesRechazadas, DocumentoNoEncontrado, EfectoDesconocido,
            ProveedorNoDisponible, RespuestaInesperada, SolicitudRechazada, TitularNoAutoriza,
        )
        repositorio = trabajador.repositorio
        forzar = bool(consulta.manifiesto.get("forzar"))
        caidas = self._fuentes_caidas(trabajador.politica.entorno, consulta)
        if caidas and not forzar:
            # No se gasta un crédito en una consulta que de todos modos quedaría parcial.
            repositorio.guardar_progreso(concesion, etapa="TERMINADA", evento="FUENTES_CAIDAS_PROVEEDOR")
            return self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
                consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="FUENTES_CAIDAS_PROVEEDOR",
                mensaje="Tusdatos informa fuentes caídas o en mantenimiento: " + ", ".join(caidas)
                        + ". No se hizo la consulta ni se gastó crédito",
                advertencia="Intente más tarde, o use «Forzar actualización» para consultar de todos modos "
                            "(el resultado quedará parcial)", estado_cobertura="DESCONOCIDA",
                fecha_inicio=consulta.admitida_en, fecha_fin=repositorio.reloj()))
        if self._verificar_documento(trabajador, concesion, consulta, solicitud):
            return None  # El documento no existe: la consulta ya quedó cerrada.
        self._vigilar_creditos(trabajador.politica.entorno)
        espera = repositorio.reservar_turno(PROVEEDOR, INTERVALO_LANZAMIENTOS)
        if espera > 0:
            return repositorio.posponer(concesion, max(espera, 1.0))
        repositorio.guardar_progreso(concesion, etapa="LANZANDO", evento="LANZAMIENTO_EXTERNO")
        try:
            lanzado = self.cliente(trabajador.politica.entorno).lanzar(
                solicitud.tipo_documento, solicitud.numero, nombre=solicitud.nombre,
                fecha_expedicion=solicitud.fecha_expedicion, forzar=forzar,
                referencia=str(consulta.id))
        except ProveedorNoDisponible:
            # No llegó al proveedor: es seguro volver a intentarlo más tarde.
            repositorio.guardar_progreso(concesion, etapa="POR_LANZAR")
            return repositorio.posponer(concesion, ESPERA_RED)
        except TitularNoAutoriza:
            repositorio.guardar_progreso(concesion, etapa="TERMINADA")
            return self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
                consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="TITULAR_NO_AUTORIZA",
                mensaje="El titular de los datos no autoriza la consulta (protección de datos personales)",
                fecha_inicio=consulta.admitida_en, fecha_fin=repositorio.reloj()))
        except DocumentoNoEncontrado:
            repositorio.guardar_progreso(concesion, etapa="TERMINADA")
            return self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
                consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="DOCUMENTO_NO_ENCONTRADO",
                mensaje=MENSAJES_NO_ENCONTRADO.get(solicitud.tipo_documento, MENSAJES_NO_ENCONTRADO["CC"]),
                advertencia="Revise el número y el tipo de documento antes de repetir la consulta",
                estado_cobertura="DESCONOCIDA", fecha_inicio=consulta.admitida_en, fecha_fin=repositorio.reloj()))
        except (CredencialesRechazadas, AccesoDenegado, SolicitudRechazada) as error:
            return self._terminar_con_fallo(repositorio, concesion, error.codigo)
        except ValueError:
            return self._terminar_con_fallo(repositorio, concesion, "DATOS_ADMITIDOS_NO_INTERPRETABLES")
        except (EfectoDesconocido, RespuestaInesperada):
            # El progreso queda en LANZANDO: nadie relanzará esta consulta automáticamente.
            return repositorio.fallar(concesion, "EFECTO_EXTERNO_DESCONOCIDO", indeterminada=True)
        if lanzado.en_cache:
            return self._desde_cache(trabajador, concesion, consulta, solicitud)
        repositorio.guardar_progreso(concesion, etapa="ESPERANDO", jobid=lanzado.jobid)
        return repositorio.posponer(concesion, ESPERA_TRAS_LANZAR)


    # ── Recuperación después del cierre (gratis) ────────────────────────────

    def revisar_pendientes(self, trabajador):
        """Recupera sin gastar créditos lo que quedó incompleto en consultas ya cerradas."""
        entorno = trabajador.politica.entorno
        if not self.disponible(entorno):
            return
        configuracion = self.cliente(entorno).configuracion
        if not getattr(configuracion, "recuperar", False):
            return
        for cerrada in self._cerradas_recientes(trabajador):
            for paso in (self._recuperar_evidencia, self._programar_recarga):
                try:
                    paso(trabajador, cerrada)
                except Exception as error:  # Una consulta con problemas no frena la revisión de las demás.
                    registro.error("Tusdatos: no se pudo revisar la consulta cerrada %s: %s", cerrada.id, type(error).__name__)

    def _cerradas_recientes(self, trabajador):
        """Consultas externas cerradas en la ventana de recuperación que tienen reporte de Tusdatos."""
        from sqlalchemy import select
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION, PROVEEDOR
        from infrastructure.persistencia.modelos_listas import (
            ConsultaLista, EventoConsulta, EvidenciaConsulta, ProgresoConsultaExterna,
        )
        desde = trabajador.repositorio.reloj() - VENTANA_RECUPERACION
        with trabajador.sesiones() as sesion:
            filas = sesion.execute(select(ConsultaLista, ProgresoConsultaExterna.reporte_id, ProgresoConsultaExterna.respuesta_filtrada)
                .join(ProgresoConsultaExterna, ProgresoConsultaExterna.consulta_id == ConsultaLista.id)
                .where(ConsultaLista.implementacion == self.implementacion, ConsultaLista.proveedor == PROVEEDOR,
                       ConsultaLista.estado.in_(("COMPLETADA", "PARCIAL", "FALLIDA")), ConsultaLista.finalizada_en >= desde,
                       ProgresoConsultaExterna.reporte_id.is_not(None))
                .order_by(ConsultaLista.finalizada_en, ConsultaLista.id)).all()
            filas = [f for f in filas if (f[0].manifiesto or {}).get("adaptador") == ADAPTADOR_VERSION]
            ids = [f[0].id for f in filas]
            evidencias, eventos = {}, {}
            if ids:
                for consulta_id, tipo in sesion.execute(select(EvidenciaConsulta.consulta_id, EvidenciaConsulta.tipo)
                                                         .where(EvidenciaConsulta.consulta_id.in_(ids))):
                    evidencias.setdefault(consulta_id, set()).add(tipo)
                for consulta_id, tipo in sesion.execute(select(EventoConsulta.consulta_id, EventoConsulta.tipo)
                                                         .where(EventoConsulta.consulta_id.in_(ids))):
                    eventos.setdefault(consulta_id, set()).add(tipo)
            return [ConsultaCerrada(id=c.id, estado=c.estado, expediente_id=c.expediente_id, creado_en=c.creado_en,
                                    finalizada_en=c.finalizada_en, criterio=c.criterio_original, manifiesto=c.manifiesto,
                                    resultado=c.resultado, reporte_id=reporte_id, dest=(filtrada or {}).get("dest"),
                                    evidencias=frozenset(evidencias.get(c.id, ())), eventos=frozenset(eventos.get(c.id, ())))
                    for c, reporte_id, filtrada in filas]

    def _recuperar_evidencia(self, trabajador, cerrada):
        """Vuelve a pedir el PDF y las capturas que no llegaron antes del cierre."""
        from domain.listas.contratos import Criterio
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION, FUENTES_POR_CODIGO, traducir_criterio
        from infrastructure.listas.tusdatos.cliente import PdfPendiente
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        cliente = self.cliente(trabajador.politica.entorno)
        capturables = [c for c in cerrada.manifiesto.get("fuentes") or () if c in FUENTES_POR_CODIGO and FUENTES_POR_CODIGO[c].captura]
        falta_pdf = "PDF_PROVEEDOR" not in cerrada.evidencias
        # Solo si no se alcanzaron a pedir: si Tusdatos respondió que no hay, no hay.
        faltan_capturas = bool(getattr(cliente.configuracion, "capturas", False) and cerrada.dest and capturables
                               and "CAPTURA_PROVEEDOR" not in cerrada.evidencias
                               and "CAPTURAS_PROVEEDOR_OMITIDAS" in cerrada.eventos)
        if not (falta_pdf or faltan_capturas):
            return
        repositorio = trabajador.repositorio
        if repositorio.reclamar_reintento_evidencia(cerrada.id, ESPERAS_RECUPERACION) is None:
            return
        if falta_pdf:
            solicitud = traducir_criterio(Criterio.model_validate(cerrada.criterio))
            try:
                documento = cliente.pdf(cerrada.reporte_id, es_nit=solicitud.es_nit)
            except ErrorTusdatos:
                documento = None
            if documento is not None and not isinstance(documento, PdfPendiente):
                repositorio.agregar_evidencia_tardia(cerrada.id, "PDF_PROVEEDOR", trabajador.custodia.guardar(documento.contenido),
                                                     "application/pdf", ADAPTADOR_VERSION)
        if faltan_capturas:
            for codigo in capturables:
                try:
                    captura = cliente.captura(cerrada.dest, FUENTES_POR_CODIGO[codigo].captura)
                except (ErrorTusdatos, ValueError):
                    captura = None
                if captura is not None:
                    repositorio.agregar_evidencia_tardia(cerrada.id, "CAPTURA_PROVEEDOR", trabajador.custodia.guardar(captura.contenido),
                                                         "image/jpeg", ADAPTADOR_VERSION, fuente_codigo=codigo)

    def _programar_recarga(self, trabajador, cerrada):
        """Admite la recarga gratuita de una consulta que cerró con fuentes fallidas, si ya toca."""
        if cerrada.estado not in {"PARCIAL", "FALLIDA"} or not cerrada.resultado:
            return
        fallidas = [c.get("fuente_codigo") for c in cerrada.resultado.get("cobertura") or ()
                    if c.get("estado") == "FALLIDA" and c.get("fuente_codigo")]
        if not fallidas:
            return
        intento = int((cerrada.manifiesto.get("recupera") or {}).get("intento") or 0) + 1
        repositorio = trabajador.repositorio
        if intento > len(ESPERAS_RECUPERACION) or cerrada.finalizada_en + ESPERAS_RECUPERACION[intento - 1] > repositorio.reloj():
            return
        if self._codigos_caidos(trabajador.politica.entorno, fallidas, VIGENCIA_SALUD_RECARGA):
            return  # Recargar con la fuente caída no sirve; se vuelve a mirar en la próxima revisión.
        documento = _documento(cerrada.criterio)
        manifiesto = {**cerrada.manifiesto, "forzar": False,
                      "recupera": {"consulta_id": str(cerrada.id), "reporte_id": cerrada.reporte_id, "intento": intento}}
        with trabajador.sesiones.begin() as sesion:
            bloquear_documento(sesion, cerrada.expediente_id, documento)
            if self._hay_posterior(sesion, cerrada, documento):
                return  # Ya hay una consulta más nueva de ese documento (otra recarga o una del usuario).
            nueva = repositorio.admitir_recuperacion(cerrada.id, manifiesto, sesion_actual=sesion)
        if nueva:
            registro.info("Tusdatos: recarga automática %s de la consulta %s (intento %d)", nueva, cerrada.id, intento)

    def _hay_posterior(self, sesion, cerrada, documento) -> bool:
        from sqlalchemy import select
        from infrastructure.persistencia.modelos_listas import ConsultaLista
        filas = sesion.execute(select(ConsultaLista.criterio_original).where(
            ConsultaLista.expediente_id == cerrada.expediente_id, ConsultaLista.implementacion == self.implementacion,
            ConsultaLista.creado_en > cerrada.creado_en, ConsultaLista.id != cerrada.id))
        return any(_documento(fila.criterio_original) == documento for fila in filas)

    @staticmethod
    def _verificacion_heredada(repositorio, consulta) -> dict:
        """La recarga conserva la verificación previa del documento (y su aviso) de la consulta original."""
        from uuid import UUID
        recupera = consulta.manifiesto.get("recupera") or {}
        if not recupera.get("consulta_id"):
            return {}
        previa = repositorio.progreso_externo(UUID(recupera["consulta_id"]))
        return {"verificacion_documento": previa.verificacion_documento} if previa and previa.verificacion_documento else {}

    def _recargar_previa(self, trabajador, concesion, consulta, solicitud):
        """Primera etapa de una recarga automática: `/api/retry` sobre el reporte anterior, sin crédito."""
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos, ProveedorNoDisponible
        repositorio = trabajador.repositorio
        reporte_id = consulta.manifiesto["recupera"]["reporte_id"]
        try:
            nuevo = self.cliente(trabajador.politica.entorno).reintentar_fuentes(reporte_id, solicitud.tipo_documento)
        except ProveedorNoDisponible:
            return repositorio.posponer(concesion, ESPERA_RED)  # Recargar es gratis: repetirlo no cuesta.
        except (ErrorTusdatos, ValueError):
            # Tusdatos no admitió la recarga (por ejemplo, un reporte que ya no acepta reintentos):
            # se deja de insistir y la consulta anterior conserva su resultado.
            return self._terminar_con_fallo(repositorio, concesion, "RECARGA_NO_ADMITIDA_PROVEEDOR")
        repositorio.guardar_progreso(concesion, etapa="ESPERANDO", jobid=nuevo, recargas=1, reporte_id=reporte_id,
                                     evento="RECARGA_FUENTES_EXTERNAS")
        return repositorio.posponer(concesion, ESPERA_TRAS_LANZAR)

    # ── Verificación previa del documento (NIT y cédula de extranjería) ─────

    def _verificar_documento(self, trabajador, concesion, consulta, solicitud):
        """Valida el NIT o la CE antes de consultar listas; True si cerró la consulta (documento inexistente).

        Se hace una sola vez por consulta (queda en el progreso). Si la verificación falla o
        no se puede interpretar, la consulta sigue: nunca bloquea por un problema del servicio.
        """
        from infrastructure.listas.tusdatos.adaptador import resultado_sin_reporte
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        if solicitud.tipo_documento not in TIPOS_VERIFICABLES:
            return False
        repositorio = trabajador.repositorio
        cliente = self.cliente(trabajador.politica.entorno)
        if not getattr(cliente.configuracion, "verificar_documento", False):
            return False
        progreso = repositorio.progreso_externo(consulta.id)
        if progreso is not None and progreso.verificacion_documento is not None:
            return False  # Ya se verificó en una pasada anterior.
        try:
            verificacion = cliente.verificar_documento(solicitud.tipo_documento, solicitud.numero,
                                                       fecha_expedicion=solicitud.fecha_expedicion)
        except (ErrorTusdatos, ValueError) as error:
            codigo = getattr(error, "codigo", "DATOS_NO_VERIFICABLES")
            repositorio.guardar_progreso(concesion, evento="VERIFICACION_DOCUMENTO_FALLIDA",
                                         verificacion_documento={"tipo": solicitud.tipo_documento,
                                                                 "resultado": "SIN_VERIFICAR", "motivo": codigo})
            registro.info("Tusdatos: no se pudo verificar el documento (%s); la consulta sigue", codigo)
            return False
        if verificacion.no_encontrado:
            resultado = "NO_ENCONTRADO"
        elif verificacion.vigente is False:
            resultado = "NO_VIGENTE"
        elif verificacion.vigente:
            resultado = "VIGENTE"
        else:
            resultado = "SIN_DATO"
        guardado = {"tipo": solicitud.tipo_documento, "resultado": resultado, "estado": verificacion.estado,
                    "avisos": list(verificacion.avisos)}
        if resultado != "NO_ENCONTRADO":
            repositorio.guardar_progreso(concesion, evento="DOCUMENTO_VERIFICADO", verificacion_documento=guardado)
            return False
        repositorio.guardar_progreso(concesion, etapa="TERMINADA", evento="DOCUMENTO_NO_ENCONTRADO",
                                     verificacion_documento=guardado)
        self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
            consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="DOCUMENTO_NO_ENCONTRADO",
            mensaje=MENSAJES_NO_ENCONTRADO[solicitud.tipo_documento]
                    + ". Se comprobó antes de consultar listas, así que no se hizo esa consulta",
            advertencia="Revise el número y el tipo de documento antes de repetir la consulta",
            estado_cobertura="DESCONOCIDA", fecha_inicio=consulta.admitida_en, fecha_fin=repositorio.reloj()))
        return True

    # ── CC en caché de Tusdatos: recuperación por el historial ──────────────

    def _desde_cache(self, trabajador, concesion, consulta, solicitud):
        """`launch` respondió sin jobid: se busca el reporte de esa consulta en el historial."""
        from domain.listas.contratos import Criterio
        from infrastructure.listas.tusdatos.adaptador import resultado_sin_reporte
        from infrastructure.listas.tusdatos.cliente import EstadoTrabajo
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        repositorio = trabajador.repositorio
        cliente = self.cliente(trabajador.politica.entorno)
        ahora = repositorio.reloj()
        reporte = None
        try:
            reporte_id = self._reporte_en_historial(cliente, solicitud, ahora)
            if reporte_id:
                reporte = (reporte_id, cliente.reporte(reporte_id))
        except ErrorTusdatos:
            reporte = None  # El historial no existe en el sandbox; tampoco se adivina si falla.
        if reporte is None:
            repositorio.guardar_progreso(concesion, etapa="TERMINADA")
            return self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
                consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="RESULTADO_EN_CACHE_SIN_REFERENCIA",
                mensaje="Tusdatos devolvió una consulta anterior (últimas 6 horas) sin referencia a su reporte, "
                        "y no se encontró en el historial de la cuenta",
                advertencia="Use «Forzar actualización» para obtener un reporte nuevo", estado_cobertura="DESCONOCIDA",
                fecha_inicio=consulta.admitida_en, fecha_fin=ahora))
        reporte_id, documento = reporte
        repositorio.guardar_progreso(concesion, reporte_id=reporte_id, evento="REPORTE_RECUPERADO_DE_HISTORIAL")
        errores = tuple(e for e in (documento.datos.get("errores") or []) if isinstance(e, str))
        estado = EstadoTrabajo(finalizado=True, reporte_id=reporte_id, errores=errores)
        # Aún en LANZANDO: no se puede posponer (se tomaría como lanzamiento interrumpido).
        return self._procesar_finalizado(trabajador, concesion, consulta, Criterio.model_validate(consulta.criterio),
                                         solicitud, repositorio.progreso_externo(consulta.id), estado,
                                         reporte=documento, puede_esperar=False)

    @staticmethod
    def _reporte_en_historial(cliente, solicitud, ahora) -> str | None:
        """Id del reporte más reciente de ese documento dentro de la ventana de caché de 6 h.

        Una consulta sin fecha y hora legibles no se usa: no se puede saber si es la de la caché.
        """
        from infrastructure.listas.tusdatos.cliente import HORA_COLOMBIA, limpiar_documento
        desde = ahora - VENTANA_CACHE
        previas = cliente.historial(solicitud.tipo_documento, solicitud.numero, desde.astimezone(HORA_COLOMBIA).date())
        documento = limpiar_documento(solicitud.numero)
        vigentes = [p for p in previas if p.creada_en is not None and desde <= p.creada_en <= ahora + timedelta(minutes=5)
                    and (not p.documento or p.documento == documento)]
        return max(vigentes, key=lambda p: p.creada_en).reporte_id if vigentes else None

    # ── Revisión previa (gratuita): fuentes caídas y créditos ───────────────

    def _estado_fuentes(self, entorno, vigencia=VIGENCIA_SALUD):
        """{código: estado} de Tusdatos, reutilizado `vigencia` segundos; None si no se pudo saber."""
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        guardado = self._salud.get(entorno)
        if guardado and self._monotonic() - guardado[0] < vigencia:
            return guardado[1]
        try:
            estados = {f.codigo: f.estado for f in self.cliente(entorno).estado_fuentes()}
        except ErrorTusdatos:
            estados = None  # Sin estado no se bloquea: la consulta sigue como siempre.
        self._salud[entorno] = (self._monotonic(), estados)
        if estados and entorno not in self._sin_estado_avisado:
            self._avisar_fuentes_sin_estado(estados)
            self._sin_estado_avisado.add(entorno)
        return estados

    @staticmethod
    def _avisar_fuentes_sin_estado(estados):
        """Deja constancia (una vez por proceso) de las fuentes aprobadas que Tusdatos no informa.

        Esas fuentes no se pueden revisar antes de consultar. El registro dice con qué
        códigos las informa Tusdatos en realidad, para corregir `codigos_estado` si hace falta.
        """
        from infrastructure.listas.tusdatos.adaptador import FUENTES
        faltantes = sorted(f.codigo for f in FUENTES if not f.codigos_estado & set(estados))
        if faltantes:
            registro.warning("Tusdatos sources/status no informa estas fuentes aprobadas: %s. Códigos informados: %s",
                             ", ".join(faltantes), ", ".join(sorted(estados)))

    def _codigos_caidos(self, entorno, codigos, vigencia=VIGENCIA_SALUD) -> set[str]:
        """De esos códigos de fuente, los que Tusdatos reporta caídos o en mantenimiento."""
        from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO
        if getattr(self.cliente(entorno).configuracion, "es_sandbox", False):
            return set()  # El sandbox devuelve un estado fijo (Procuraduría siempre en mantenimiento).
        estados = self._estado_fuentes(entorno, vigencia)
        if not estados:
            return set()
        return {codigo for codigo in codigos if codigo in FUENTES_POR_CODIGO
                and any(estados.get(c) in ESTADOS_CAIDOS for c in FUENTES_POR_CODIGO[codigo].codigos_estado)}

    def _fuentes_caidas(self, entorno, consulta) -> list[str]:
        """Nombres de las fuentes que deciden el resultado y Tusdatos reporta caídas."""
        from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO
        bloqueantes = [c for c in consulta.manifiesto.get("fuentes") or ()
                       if c in FUENTES_POR_CODIGO and FUENTES_POR_CODIGO[c].ausencia_bloquea]
        caidas = self._codigos_caidos(entorno, bloqueantes)
        return [FUENTES_POR_CODIGO[c].nombre for c in bloqueantes if c in caidas]

    def _vigilar_creditos(self, entorno):
        """Publica el saldo de créditos y avisa cuando está bajo; nunca bloquea la consulta."""
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        cliente = self.cliente(entorno)
        configuracion = cliente.configuracion
        if configuracion.es_sandbox:
            return  # El sandbox informa siempre 0 créditos.
        clave = (entorno, "creditos")
        guardado = self._salud.get(clave)
        if guardado and self._monotonic() - guardado[0] < VIGENCIA_SALUD:
            return
        try:
            restantes = cliente.creditos_restantes()
        except ErrorTusdatos:
            restantes = None
        self._salud[clave] = (self._monotonic(), restantes)
        if restantes is None:
            return
        try:
            cliente.metricas("Sagrilaft/Listas", {"Proveedor": "Tusdatos"}, {"TusdatosCreditosRestantes": restantes})
        except Exception:  # Las métricas nunca interrumpen la consulta.
            registro.debug("No se pudo emitir la métrica de créditos", exc_info=True)
        if restantes <= configuracion.alerta_creditos:
            registro.warning("Tusdatos: quedan %d créditos (umbral de aviso %d)", restantes, configuracion.alerta_creditos)

    def _esperar(self, trabajador, concesion, consulta, criterio, solicitud, progreso):
        from infrastructure.listas.tusdatos.errores import (
            ConsultaFallida, ErrorTusdatos, ProveedorNoDisponible, TrabajoVencido,
        )
        repositorio = trabajador.repositorio
        cliente = self.cliente(trabajador.politica.entorno)
        try:
            estado = cliente.estado(progreso.jobid)
        except ProveedorNoDisponible:
            return repositorio.posponer(concesion, ESPERA_RED)
        except TrabajoVencido:
            return self._terminar_con_fallo(repositorio, concesion, "TRABAJO_PROVEEDOR_VENCIDO", indeterminada=True)
        except ConsultaFallida:
            return self._terminar_con_fallo(repositorio, concesion, "CONSULTA_FALLIDA_PROVEEDOR")
        except ErrorTusdatos as error:
            return self._terminar_con_fallo(repositorio, concesion, error.codigo, indeterminada=True)
        if not estado.finalizado:
            return repositorio.posponer(concesion, ESPERA_SONDEO)
        return self._procesar_finalizado(trabajador, concesion, consulta, criterio, solicitud, progreso, estado)

    def _procesar_finalizado(self, trabajador, concesion, consulta, criterio, solicitud, progreso, estado,
                             reporte=None, puede_esperar=True):
        """Recarga si hace falta, interpreta el reporte y pasa a descargar el PDF."""
        from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO, interpretar_reporte
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos, ProveedorNoDisponible
        repositorio = trabajador.repositorio
        entorno = trabajador.politica.entorno
        cliente = self.cliente(entorno)
        fuentes = tuple(consulta.manifiesto.get("fuentes") or ())
        fallidas = [f for f in fuentes if f in FUENTES_POR_CODIGO and set(FUENTES_POR_CODIGO[f].errores) & set(estado.errores)]
        caidas = self._codigos_caidos(entorno, fallidas, VIGENCIA_SALUD_RECARGA) if fallidas else set()
        if fallidas and progreso.recargas == 0:
            if caidas and puede_esperar and progreso.vence_en - repositorio.reloj() > MARGEN_RECARGA:
                # Tusdatos: recargar con la fuente caída no sirve. Se espera a que vuelva.
                return repositorio.posponer(concesion, ESPERA_FUENTE_CAIDA)
            if caidas:
                # Sin tiempo para esperar: se cierra parcial sin gastar la única recarga.
                repositorio.guardar_progreso(concesion, recargas=1, evento="RECARGA_OMITIDA_FUENTES_CAIDAS")
            else:
                # Recarga gratuita de las fuentes con error, una sola vez.
                try:
                    nuevo = cliente.reintentar_fuentes(estado.reporte_id, solicitud.tipo_documento)
                except ErrorTusdatos:
                    nuevo = None
                if nuevo:
                    repositorio.guardar_progreso(concesion, etapa="ESPERANDO", jobid=nuevo, recargas=1,
                                                 reporte_id=estado.reporte_id, evento="RECARGA_FUENTES_EXTERNAS")
                    return repositorio.posponer(concesion, ESPERA_TRAS_LANZAR)
                repositorio.guardar_progreso(concesion, recargas=1)
        if reporte is None:
            try:
                reporte = cliente.reporte(estado.reporte_id)
            except ProveedorNoDisponible:
                return repositorio.posponer(concesion, ESPERA_RED)
            except ErrorTusdatos as error:
                return self._terminar_con_fallo(repositorio, concesion, error.codigo, indeterminada=True)
        interpretacion = interpretar_reporte(reporte.datos, consulta_id=consulta.id, solicitud=solicitud, criterio=criterio,
            fuentes=fuentes or None, errores_estado=estado.errores, fecha_inicio=consulta.admitida_en,
            fecha_fin=repositorio.reloj(), validado=estado.validado, fuentes_caidas=frozenset(caidas),
            documento_no_vigente=_aviso_no_vigente(progreso), recuperacion=_aviso_recuperacion(consulta))
        # Solo el subconjunto aprobado y la huella de la respuesta completa llegan a PostgreSQL.
        repositorio.guardar_progreso(concesion, etapa="DESCARGANDO_PDF", reporte_id=estado.reporte_id,
                                     huella_respuesta=reporte.sha256, respuesta_filtrada=interpretacion.respuesta_filtrada)
        repositorio.guardar_borrador(concesion, interpretacion.resultado)
        return self._cerrar(trabajador, concesion, consulta, solicitud)

    def _cerrar(self, trabajador, concesion, consulta, solicitud):
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION
        from infrastructure.listas.tusdatos.cliente import PdfPendiente
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos, ProveedorNoDisponible
        repositorio = trabajador.repositorio
        progreso = repositorio.progreso_externo(consulta.id)
        if progreso is not None and progreso.etapa == "DESCARGANDO_PDF":
            documento = None
            if repositorio.reloj() < progreso.vence_en:
                try:
                    documento = self.cliente(trabajador.politica.entorno).pdf(progreso.reporte_id, es_nit=solicitud.es_nit)
                except ProveedorNoDisponible:
                    return repositorio.posponer(concesion, ESPERA_RED)
                except ErrorTusdatos:
                    documento = None
                if isinstance(documento, PdfPendiente):
                    return repositorio.posponer(concesion, documento.reintentar_en)
            custodiado = False
            if documento is not None:
                try:
                    objeto = trabajador.custodia.guardar(documento.contenido)
                    repositorio.agregar_evidencia_proveedor(concesion, "PDF_PROVEEDOR", objeto, "application/pdf", ADAPTADOR_VERSION)
                    custodiado = True
                except OSError:
                    custodiado = False
            repositorio.guardar_progreso(concesion, evento="PDF_PROVEEDOR_CUSTODIADO" if custodiado else "PDF_PROVEEDOR_NO_DISPONIBLE")
            repositorio.guardar_progreso(concesion, etapa="TERMINADA", evento=self._custodiar_capturas(trabajador, concesion, consulta, progreso))
        return self._informe_y_cierre(repositorio, concesion)

    def _custodiar_capturas(self, trabajador, concesion, consulta, progreso) -> str:
        """Guarda las capturas por fuente del reporte; devuelve el evento con que se deja constancia.

        Una captura que falle o no exista no detiene nada: el PDF y el JSON ya son la evidencia
        principal. No se repite en otra pasada, para no alargar el cierre.
        """
        from infrastructure.listas.tusdatos.adaptador import ADAPTADOR_VERSION, FUENTES_POR_CODIGO
        from infrastructure.listas.tusdatos.errores import ErrorTusdatos
        repositorio = trabajador.repositorio
        cliente = self.cliente(trabajador.politica.entorno)
        dest = (progreso.respuesta_filtrada or {}).get("dest")
        if not getattr(cliente.configuracion, "capturas", False) or not dest or repositorio.reloj() >= progreso.vence_en:
            return "CAPTURAS_PROVEEDOR_OMITIDAS"
        custodiadas = 0
        for codigo in consulta.manifiesto.get("fuentes") or ():
            fuente = FUENTES_POR_CODIGO.get(codigo)
            if fuente is None or not fuente.captura:
                continue
            try:
                captura = cliente.captura(dest, fuente.captura)
            except (ErrorTusdatos, ValueError):
                captura = None
            if captura is None:
                continue
            try:
                objeto = trabajador.custodia.guardar(captura.contenido)
                if repositorio.agregar_evidencia_proveedor(concesion, "CAPTURA_PROVEEDOR", objeto, "image/jpeg",
                                                           ADAPTADOR_VERSION, fuente_codigo=codigo):
                    custodiadas += 1
            except OSError:
                continue
        return "CAPTURAS_PROVEEDOR_CUSTODIADAS" if custodiadas else "CAPTURAS_PROVEEDOR_NO_DISPONIBLES"

    def _cerrar_con_resultado(self, trabajador, concesion, resultado):
        trabajador.repositorio.guardar_borrador(concesion, resultado)
        return self._informe_y_cierre(trabajador.repositorio, concesion)

    @staticmethod
    def _informe_y_cierre(repositorio, concesion):
        from domain.listas.errores import ErrorIntegridadEvidencia
        try:
            repositorio.preparar_informe(concesion)
            repositorio.cerrar(concesion)
        except (ErrorIntegridadEvidencia, OSError):
            repositorio.fallar(concesion, "CUSTODIA_NO_DISPONIBLE")

    @staticmethod
    def _terminar_con_fallo(repositorio, concesion, codigo, indeterminada=False):
        # El progreso se cierra antes que la consulta: después de cerrarla ya no cambia.
        if repositorio.progreso_externo(concesion.consulta_id) is not None:
            repositorio.guardar_progreso(concesion, etapa="TERMINADA")
        repositorio.fallar(concesion, codigo, indeterminada=indeterminada)
