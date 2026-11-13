"""Modalidad externa (Tusdatos): admisión por documento y protocolo por etapas en el trabajador.

Cada pasada del trabajador avanza una etapa y libera la consulta hasta el próximo intento:

    POR_LANZAR ──(turno de 5 s)──► LANZANDO ──► ESPERANDO ──► DESCARGANDO_PDF ──► TERMINADA
                                     │             │ (sondeo; una recarga gratuita
                                     │             │  si fallaron fuentes requeridas)
                                     └─ si el trabajador cae aquí, la consulta queda
                                        INDETERMINADA y nunca se relanza sola.

- LANZANDO se confirma en la base ANTES de llamar a `launch`, que gasta un crédito.
- El plazo es de 15 minutos desde la admisión; vencido, se cierra NO_CONCLUYENTE.
- El PDF del proveedor se intenta dentro del mismo plazo; si no llega, la consulta se
  cierra igual y queda un evento PDF_PROVEEDOR_NO_DISPONIBLE (el id del reporte queda
  guardado para descargarlo después).
"""
from datetime import timedelta

from domain.listas.puertos import ListasNoDisponibles
from services.listas.modalidad_base import crear_grupo_por_documento, datos_sujeto

PLAZO = timedelta(minutes=15)
INTERVALO_LANZAMIENTOS = 5.0   # Tusdatos exige 5 s entre lanzamientos.
ESPERA_TRAS_LANZAR = 15.0      # Una consulta tarda en promedio un minuto.
ESPERA_SONDEO = 5.0            # Frecuencia de sondeo recomendada por Tusdatos.
ESPERA_RED = 15.0
CONCESION_PASADA = 300         # Cubre la llamada más lenta (PDF) con sus reintentos.


class ModalidadExterna:
    implementacion = "externo"
    version_contrato = "2.0"

    def __init__(self, fabrica_cliente=None):
        # Las pruebas inyectan un cliente con transporte simulado; en ejecución se arma desde el entorno.
        self._fabrica = fabrica_cliente
        self._clientes = {}

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

    def crear(self, servicio, solicitud, clave):
        from domain.listas.contratos import SolicitudIdempotente
        from infrastructure.listas.tusdatos.adaptador import PROVEEDOR, traducir_criterio
        traducida = traducir_criterio(solicitud.criterio)  # ValueError → 422, sin gastar créditos
        return servicio.repositorio.admitir(servicio.actor, SolicitudIdempotente(clave=clave, solicitud=solicitud),
                                            PROVEEDOR, self.manifiesto(servicio.entorno, traducida.sujeto))

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

        return crear_grupo_por_documento(servicio, expediente_id, clave, sesion, proveedor=PROVEEDOR,
                                         criterio_para=criterio_para, manifiesto_para=manifiesto_para)

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
            repositorio.guardar_progreso(concesion, etapa="POR_LANZAR", vence_en=consulta.admitida_en + PLAZO)
            progreso = repositorio.progreso_externo(consulta.id)
        if progreso.etapa == "TERMINADA":
            return repositorio.fallar(concesion, "EJECUCION_INTERRUMPIDA")
        if repositorio.reloj() >= progreso.vence_en:
            if progreso.etapa == "POR_LANZAR":
                return self._terminar_con_fallo(repositorio, concesion, "TIEMPO_AGOTADO_SIN_LANZAR")
            return self._terminar_con_fallo(repositorio, concesion, "TIEMPO_AGOTADO_PROVEEDOR", indeterminada=True)
        if progreso.etapa == "POR_LANZAR":
            return self._lanzar(trabajador, concesion, consulta, solicitud)
        if progreso.etapa == "ESPERANDO":
            return self._esperar(trabajador, concesion, consulta, criterio, solicitud, progreso)
        # LANZANDO sin borrador no debería llegar aquí: `reclamar` ya la deja indeterminada.
        return repositorio.fallar(concesion, "EFECTO_EXTERNO_DESCONOCIDO", indeterminada=True)

    def _lanzar(self, trabajador, concesion, consulta, solicitud):
        from infrastructure.listas.tusdatos.adaptador import PROVEEDOR, resultado_sin_reporte
        from infrastructure.listas.tusdatos.errores import (
            AccesoDenegado, CredencialesRechazadas, EfectoDesconocido, ProveedorNoDisponible,
            RespuestaInesperada, SolicitudRechazada, TitularNoAutoriza,
        )
        repositorio = trabajador.repositorio
        espera = repositorio.reservar_turno(PROVEEDOR, INTERVALO_LANZAMIENTOS)
        if espera > 0:
            return repositorio.posponer(concesion, max(espera, 1.0))
        repositorio.guardar_progreso(concesion, etapa="LANZANDO", evento="LANZAMIENTO_EXTERNO")
        try:
            lanzado = self.cliente(trabajador.politica.entorno).lanzar(
                solicitud.tipo_documento, solicitud.numero, nombre=solicitud.nombre,
                fecha_expedicion=solicitud.fecha_expedicion, forzar=bool(consulta.manifiesto.get("forzar")),
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
        except (CredencialesRechazadas, AccesoDenegado, SolicitudRechazada) as error:
            return self._terminar_con_fallo(repositorio, concesion, error.codigo)
        except ValueError:
            return self._terminar_con_fallo(repositorio, concesion, "DATOS_ADMITIDOS_NO_INTERPRETABLES")
        except (EfectoDesconocido, RespuestaInesperada):
            # El progreso queda en LANZANDO: nadie relanzará esta consulta automáticamente.
            return repositorio.fallar(concesion, "EFECTO_EXTERNO_DESCONOCIDO", indeterminada=True)
        if lanzado.en_cache:
            repositorio.guardar_progreso(concesion, etapa="TERMINADA")
            return self._cerrar_con_resultado(trabajador, concesion, resultado_sin_reporte(
                consulta_id=consulta.id, sujeto=solicitud.sujeto, codigo="RESULTADO_EN_CACHE_SIN_REFERENCIA",
                mensaje="Tusdatos devolvió una consulta anterior (últimas 6 horas) sin referencia a su reporte",
                advertencia="Use «Forzar actualización» para obtener un reporte nuevo", estado_cobertura="DESCONOCIDA",
                fecha_inicio=consulta.admitida_en, fecha_fin=repositorio.reloj()))
        repositorio.guardar_progreso(concesion, etapa="ESPERANDO", jobid=lanzado.jobid)
        return repositorio.posponer(concesion, ESPERA_TRAS_LANZAR)

    def _esperar(self, trabajador, concesion, consulta, criterio, solicitud, progreso):
        from infrastructure.listas.tusdatos.adaptador import FUENTES_POR_CODIGO, interpretar_reporte
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
        fuentes = tuple(consulta.manifiesto.get("fuentes") or ())
        fallidas = [f for f in fuentes if f in FUENTES_POR_CODIGO and set(FUENTES_POR_CODIGO[f].errores) & set(estado.errores)]
        if fallidas and progreso.recargas == 0:
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
        try:
            reporte = cliente.reporte(estado.reporte_id)
        except ProveedorNoDisponible:
            return repositorio.posponer(concesion, ESPERA_RED)
        except ErrorTusdatos as error:
            return self._terminar_con_fallo(repositorio, concesion, error.codigo, indeterminada=True)
        interpretacion = interpretar_reporte(reporte.datos, consulta_id=consulta.id, solicitud=solicitud, criterio=criterio,
            fuentes=fuentes or None, errores_estado=estado.errores, fecha_inicio=consulta.admitida_en,
            fecha_fin=repositorio.reloj())
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
            repositorio.guardar_progreso(concesion, etapa="TERMINADA",
                                         evento="PDF_PROVEEDOR_CUSTODIADO" if custodiado else "PDF_PROVEEDOR_NO_DISPONIBLE")
        return self._informe_y_cierre(repositorio, concesion)

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
