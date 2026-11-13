"""Errores del protocolo Tusdatos.

Los mensajes nunca incluyen el cuerpo de la respuesta, documentos ni nombres: solo la
operación y el código HTTP. `reintentable` dice si repetir la MISMA llamada es seguro.
"""


class ErrorTusdatos(Exception):
    codigo = "ERROR_PROVEEDOR"
    reintentable = False

    def __init__(self, operacion: str, estado_http: int | None = None, detalle: str = ""):
        self.operacion, self.estado_http = operacion, estado_http
        texto = f"Tusdatos {operacion}: {self.codigo}"
        if estado_http is not None:
            texto += f" (HTTP {estado_http})"
        super().__init__(texto + (f". {detalle}" if detalle else ""))


class CredencialesRechazadas(ErrorTusdatos):
    codigo = "CREDENCIALES_RECHAZADAS"


class TitularNoAutoriza(ErrorTusdatos):
    """403 de protección de datos: el titular no autoriza la consulta. No se repite."""
    codigo = "TITULAR_NO_AUTORIZA"


class AccesoDenegado(ErrorTusdatos):
    """403 distinto al de protección de datos (plan, créditos o permisos de la cuenta)."""
    codigo = "ACCESO_DENEGADO_PROVEEDOR"


class SolicitudRechazada(ErrorTusdatos):
    codigo = "SOLICITUD_RECHAZADA"


class DocumentoNoEncontrado(ErrorTusdatos):
    """400 al lanzar: la fuente oficial no tiene ese documento (NIT en RUES, CE en Migración)."""
    codigo = "DOCUMENTO_NO_ENCONTRADO"


class TrabajoVencido(ErrorTusdatos):
    """El jobid no existe o venció (vigencia de 2 horas)."""
    codigo = "TRABAJO_VENCIDO"


class ConsultaFallida(ErrorTusdatos):
    """Tusdatos informa que la consulta falló de su lado (500 en el estado del trabajo)."""
    codigo = "CONSULTA_FALLIDA_PROVEEDOR"


class ProveedorNoDisponible(ErrorTusdatos):
    """No hubo efecto en el proveedor (no se conectó, o una lectura falló): repetir es seguro."""
    codigo = "PROVEEDOR_NO_DISPONIBLE"
    reintentable = True


class EfectoDesconocido(ErrorTusdatos):
    """El lanzamiento pudo llegar al proveedor y consumir un crédito; repetirlo no es seguro."""
    codigo = "EFECTO_EXTERNO_DESCONOCIDO"


class RespuestaInesperada(ErrorTusdatos):
    codigo = "RESPUESTA_INESPERADA"
