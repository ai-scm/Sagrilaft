"""Cliente HTTP de Tusdatos: lanzar, consultar estado, reporte JSON, PDF, recarga y salud.

Solo conoce el protocolo. No decide qué fuentes interesan ni interpreta coincidencias:
eso lo hace el adaptador de listas. Reglas que aplica:

- `lanzar` consume créditos: nunca se reintenta automáticamente. Si la petición pudo
  llegar al proveedor y no hubo respuesta clara, levanta `EfectoDesconocido`.
- Las lecturas (estado, reporte, PDF, salud) se reintentan ante fallas de red o 5xx.
- Un interruptor corta las llamadas tras fallas seguidas de disponibilidad.
- Errores, registros y métricas no llevan documentos, nombres ni cuerpos de respuesta.
"""
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import date

import httpx

from infrastructure.listas.tusdatos.configuracion import ConfiguracionTusdatos
from infrastructure.listas.tusdatos.errores import (
    AccesoDenegado, ConsultaFallida, CredencialesRechazadas, EfectoDesconocido,
    ProveedorNoDisponible, RespuestaInesperada, SolicitudRechazada, TitularNoAutoriza, TrabajoVencido,
)

registro = logging.getLogger(__name__)

# Alcance SAGRILAFT aprobado: persona natural (CC, CE, pasaporte) y jurídica (NIT).
TIPOS_DOCUMENTO = frozenset({"CC", "CE", "PP", "NIT"})
_IDENTIFICADOR = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_SIN_EFECTO = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.UnsupportedProtocol)


@dataclass(frozen=True)
class Lanzamiento:
    jobid: str | None
    validado: bool | None
    nombre_resuelto: str | None

    @property
    def en_cache(self) -> bool:
        """CC consultada en las últimas 6 h sin `force`: Tusdatos no entrega jobid."""
        return self.jobid is None


@dataclass(frozen=True)
class EstadoTrabajo:
    finalizado: bool
    reporte_id: str | None = None
    hallazgo: bool | None = None
    errores: tuple[str, ...] = ()
    porcentaje: int | None = None
    # False si Tusdatos no pudo validar el documento; None si no aplica (pasaporte, NIT).
    validado: bool | None = None


@dataclass(frozen=True)
class DocumentoReporte:
    contenido: bytes
    datos: dict

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.contenido).hexdigest()


@dataclass(frozen=True)
class DocumentoPdf:
    contenido: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.contenido).hexdigest()


@dataclass(frozen=True)
class PdfPendiente:
    reintentar_en: int


@dataclass(frozen=True)
class EstadoFuente:
    codigo: str
    estado: str  # operational | under_maintenance | source_down


class Interruptor:
    """Tras `umbral` fallas de disponibilidad seguidas, rechaza llamadas durante `enfriamiento` s."""

    def __init__(self, umbral=5, enfriamiento=60.0, reloj=time.monotonic):
        self.umbral, self.enfriamiento, self.reloj = umbral, enfriamiento, reloj
        self.fallas, self.abierto_hasta = 0, 0.0

    def permitir(self, operacion):
        if self.reloj() < self.abierto_hasta:
            raise ProveedorNoDisponible(operacion, detalle="Interruptor abierto tras fallas seguidas")

    def exito(self):
        self.fallas = 0

    def falla(self):
        self.fallas += 1
        if self.fallas >= self.umbral:
            self.abierto_hasta, self.fallas = self.reloj() + self.enfriamiento, 0


def limpiar_documento(numero: str) -> str:
    """Quita los separadores que Tusdatos no admite (puntos, comas, guiones y espacios)."""
    return re.sub(r"[.,\s-]", "", str(numero))


def _identificador(valor: str, operacion: str) -> str:
    if not isinstance(valor, str) or not _IDENTIFICADOR.match(valor):
        raise RespuestaInesperada(operacion, detalle="Identificador del proveedor no válido")
    return valor


class ClienteTusdatos:
    def __init__(self, configuracion: ConfiguracionTusdatos, transporte: httpx.BaseTransport | None = None,
                 interruptor: Interruptor | None = None, dormir=time.sleep, reintentos_lectura: int = 2,
                 metricas=None):
        self.configuracion = configuracion
        self.interruptor = interruptor or Interruptor()
        self.dormir, self.reintentos_lectura = dormir, reintentos_lectura
        if metricas is None:
            from infrastructure.observabilidad.emf_logger import emitir_metrica_emf as metricas
        self.metricas = metricas
        encabezados = {"Accept": "application/json"}
        autenticacion = None
        if configuracion.token:
            encabezados["Authorization"] = f"Bearer {configuracion.token}"
        else:
            autenticacion = httpx.BasicAuth(configuracion.usuario, configuracion.clave)
        self._http = httpx.Client(base_url=configuracion.url_base, headers=encabezados, auth=autenticacion,
            timeout=httpx.Timeout(configuracion.tiempo_lectura, connect=configuracion.tiempo_conexion),
            transport=transporte, follow_redirects=False)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()

    def cerrar(self):
        self._http.close()

    # ── Operaciones ───────────────────────────────────────────────────────────

    def lanzar(self, tipo_documento: str, numero: str, *, nombre: str | None = None,
               fecha_expedicion: date | None = None, forzar: bool = False, referencia: str | None = None) -> Lanzamiento:
        if tipo_documento not in TIPOS_DOCUMENTO:
            raise ValueError("Tipo de documento fuera del alcance SAGRILAFT")
        documento = limpiar_documento(numero)
        if not documento or (tipo_documento != "PP" and not documento.isdigit()):
            raise ValueError("Número de documento no válido para el tipo")
        if tipo_documento == "PP" and not (nombre and len(nombre.strip()) >= 5):
            raise ValueError("Pasaporte requiere el nombre completo")
        if tipo_documento == "CE" and fecha_expedicion is None:
            raise ValueError("Cédula de extranjería requiere fecha de expedición")
        cuerpo = {"doc": documento, "typedoc": tipo_documento, "force": bool(forzar)}
        if tipo_documento == "PP":
            cuerpo["name"] = nombre.strip()
        if fecha_expedicion is not None:
            cuerpo["fechaE"] = fecha_expedicion.strftime("%d/%m/%Y")
        if referencia:
            cuerpo["webhook_reference"] = referencia[:250]
        respuesta = self._llamar("lanzar", "POST", "/api/launch", json=cuerpo, reintentos=0, con_efecto=True)
        if respuesta.status_code == 403:
            raise self._error_403(respuesta)
        self._exigir(respuesta, "lanzar", {200})
        datos = self._json(respuesta, "lanzar")
        jobid = datos.get("jobid")
        return Lanzamiento(jobid=_identificador(jobid, "lanzar") if jobid is not None else None,
                           validado=datos.get("validado"), nombre_resuelto=datos.get("nombre"))

    def estado(self, jobid: str) -> EstadoTrabajo:
        ruta = f"/api/results/{_identificador(jobid, 'estado')}"
        # 500 aquí significa «consulta fallida», no indisponibilidad: no se reintenta.
        respuesta = self._llamar("estado", "GET", ruta, reintentar_5xx=False)
        if respuesta.status_code == 404:
            raise TrabajoVencido("estado", 404)
        if respuesta.status_code == 500:
            raise ConsultaFallida("estado", 500)
        self._exigir(respuesta, "estado", {200, 207})
        datos = self._json(respuesta, "estado")
        if respuesta.status_code == 207 or datos.get("estado") == "procesando":
            porcentaje = datos.get("percentage")
            return EstadoTrabajo(finalizado=False, porcentaje=porcentaje if isinstance(porcentaje, int) else None)
        if datos.get("estado") != "finalizado":
            raise RespuestaInesperada("estado", respuesta.status_code, "Estado desconocido")
        errores = datos.get("errores") or []
        if not isinstance(errores, list) or not all(isinstance(e, str) for e in errores):
            raise RespuestaInesperada("estado", respuesta.status_code, "Lista de errores no válida")
        hallazgo, validado = datos.get("hallazgo"), datos.get("validado")
        return EstadoTrabajo(finalizado=True, reporte_id=_identificador(datos.get("id"), "estado"),
                             hallazgo=hallazgo if isinstance(hallazgo, bool) else None, errores=tuple(errores),
                             validado=validado if isinstance(validado, bool) else None)

    def reporte(self, reporte_id: str) -> DocumentoReporte:
        respuesta = self._llamar("reporte", "GET", f"/api/report_json/{_identificador(reporte_id, 'reporte')}")
        self._exigir(respuesta, "reporte", {200})
        datos = self._json(respuesta, "reporte")
        if not isinstance(datos, dict):
            raise RespuestaInesperada("reporte", 200, "El reporte no es un objeto")
        return DocumentoReporte(contenido=respuesta.content, datos=datos)

    def pdf(self, reporte_id: str, es_nit: bool) -> DocumentoPdf | PdfPendiente:
        base = "/api/v2/report_nit_pdf" if es_nit else "/api/v2/report_pdf"
        # async=true: si aún se construye, responde 202 de inmediato en vez de bloquear.
        respuesta = self._llamar("pdf", "GET", f"{base}/{_identificador(reporte_id, 'pdf')}",
                                 params={"async": "true"}, tiempo=self.configuracion.tiempo_pdf)
        if respuesta.status_code == 202:
            try:
                espera = int(respuesta.headers.get("Retry-After", "10"))
            except ValueError:
                espera = 10
            return PdfPendiente(reintentar_en=min(max(espera, 1), 300))
        self._exigir(respuesta, "pdf", {200})
        if not respuesta.content.startswith(b"%PDF-"):
            raise RespuestaInesperada("pdf", 200, "El proveedor no entregó un PDF")
        return DocumentoPdf(contenido=respuesta.content)

    def reintentar_fuentes(self, reporte_id: str, tipo_documento: str) -> str:
        """Vuelve a consultar las fuentes con error sin consumir créditos; devuelve un jobid nuevo."""
        if tipo_documento not in TIPOS_DOCUMENTO:
            raise ValueError("Tipo de documento fuera del alcance SAGRILAFT")
        base = "/api/retry_nit" if tipo_documento == "NIT" else "/api/retry"
        respuesta = self._llamar("recarga", "GET", f"{base}/{_identificador(reporte_id, 'recarga')}",
                                 params={"typedoc": tipo_documento}, reintentos=0)
        self._exigir(respuesta, "recarga", {200})
        return _identificador(self._json(respuesta, "recarga").get("jobid"), "recarga")

    def estado_fuentes(self) -> tuple[EstadoFuente, ...]:
        respuesta = self._llamar("estado_fuentes", "GET", "/api/v1/sources/status", params={"country": "CO"})
        self._exigir(respuesta, "estado_fuentes", {200})
        fuentes = self._json(respuesta, "estado_fuentes").get("sources")
        if not isinstance(fuentes, list):
            raise RespuestaInesperada("estado_fuentes", 200, "Lista de fuentes no válida")
        return tuple(EstadoFuente(codigo=str(f.get("code")), estado=str(f.get("status")))
                     for f in fuentes if isinstance(f, dict) and f.get("code"))

    def creditos_restantes(self) -> int | None:
        respuesta = self._llamar("plan", "GET", "/api/plans", params={"exclude": "checks"})
        self._exigir(respuesta, "plan", {200})
        cantidad = self._json(respuesta, "plan").get("amount")
        return cantidad if isinstance(cantidad, int) else None

    # ── Transporte ────────────────────────────────────────────────────────────

    def _llamar(self, operacion, metodo, ruta, *, reintentos=None, con_efecto=False, reintentar_5xx=True,
                tiempo=None, **opciones):
        reintentos = self.reintentos_lectura if reintentos is None else reintentos
        if tiempo is not None:
            opciones["timeout"] = httpx.Timeout(tiempo, connect=self.configuracion.tiempo_conexion)
        for intento in range(reintentos + 1):
            self.interruptor.permitir(operacion)
            inicio, estado_http = time.monotonic(), None
            try:
                respuesta = self._http.request(metodo, ruta, **opciones)
            except _SIN_EFECTO:
                error = ProveedorNoDisponible(operacion, detalle="No se pudo conectar")
            except httpx.HTTPError:
                error = (EfectoDesconocido(operacion, detalle="Sin respuesta tras enviar el lanzamiento") if con_efecto
                         else ProveedorNoDisponible(operacion, detalle="Sin respuesta del proveedor"))
            else:
                estado_http = respuesta.status_code
                if estado_http >= 500 and con_efecto:
                    # El proveedor recibió el lanzamiento; no sabemos si consumió el crédito.
                    error = EfectoDesconocido(operacion, estado_http)
                elif estado_http >= 500 and reintentar_5xx:
                    error = ProveedorNoDisponible(operacion, estado_http)
                elif estado_http == 429:
                    error = ProveedorNoDisponible(operacion, 429, "Límite de peticiones del proveedor")
                else:
                    self._medir(operacion, inicio, estado_http)
                    self.interruptor.exito()
                    return respuesta
            self._medir(operacion, inicio, estado_http)
            self.interruptor.falla()
            if isinstance(error, EfectoDesconocido) or intento == reintentos:
                registro.warning("Tusdatos %s falló: %s", operacion, error.codigo)
                raise error
            self.dormir(0.5 * (2 ** intento))
        raise AssertionError("inalcanzable")  # pragma: no cover

    def _medir(self, operacion, inicio, estado_http):
        exito = estado_http is not None and estado_http < 500
        try:
            self.metricas("Sagrilaft/Listas", {"Proveedor": "Tusdatos", "Operacion": operacion},
                          {"TusdatosLatency": int((time.monotonic() - inicio) * 1000),
                           "TusdatosExito": 1 if exito else 0, "TusdatosError": 0 if exito else 1})
        except Exception:  # Las métricas nunca interrumpen la consulta.
            registro.debug("No se pudo emitir la métrica de Tusdatos", exc_info=True)

    @staticmethod
    def _exigir(respuesta, operacion, esperados):
        estado = respuesta.status_code
        if estado in esperados:
            return
        if estado == 401:
            raise CredencialesRechazadas(operacion, 401)
        if estado == 403:
            raise AccesoDenegado(operacion, 403)
        if estado in {400, 404, 422}:
            raise SolicitudRechazada(operacion, estado)
        raise RespuestaInesperada(operacion, estado)

    @staticmethod
    def _error_403(respuesta):
        try:
            mensaje = str(respuesta.json().get("error", ""))
        except (ValueError, AttributeError):
            mensaje = ""
        return TitularNoAutoriza("lanzar", 403) if "titular" in mensaje.casefold() else AccesoDenegado("lanzar", 403)

    @staticmethod
    def _json(respuesta, operacion):
        try:
            datos = respuesta.json()
        except ValueError:
            raise RespuestaInesperada(operacion, respuesta.status_code, "La respuesta no es JSON") from None
        if not isinstance(datos, dict):
            raise RespuestaInesperada(operacion, respuesta.status_code, "La respuesta no es un objeto")
        return datos
