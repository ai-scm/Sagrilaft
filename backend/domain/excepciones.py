"""
Excepciones de dominio compartidas.

Objetivo: mantener la capa de negocio libre de HTTP y evitar duplicados
de excepciones con el mismo significado en distintos servicios.
"""


class FormularioNoEncontradoError(Exception):
    """Excepcion de dominio: el formulario solicitado no existe."""

    def __init__(self, formulario_id: str) -> None:
        self.formulario_id = formulario_id
        super().__init__(f"Formulario '{formulario_id}' no encontrado")


class FormularioNoEditableError(Exception):
    """Excepcion de dominio: la operacion no es valida para el estado actual del formulario."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)


class FormularioYaEnviadoError(Exception):
    """
    Excepcion de dominio: el formulario existe pero ya fue enviado y no es editable/recuperable como borrador.
    """


class DocumentoNoEncontradoError(Exception):
    """Excepcion de dominio: el documento solicitado no existe o fue eliminado."""

    def __init__(self, formulario_id: str, doc_id: str) -> None:
        self.formulario_id = formulario_id
        self.doc_id = doc_id
        super().__init__(f"Documento '{doc_id}' no encontrado para formulario '{formulario_id}'")


class ContraparteInvalidaError(Exception):
    """Excepcion de dominio: el tipo de contraparte no corresponde a un valor reconocido."""

    def __init__(self, tipo_contraparte: str) -> None:
        self.tipo_contraparte = tipo_contraparte
        super().__init__(
            f"Tipo de contraparte no reconocido: '{tipo_contraparte}'. "
            "Valores válidos: 'cliente', 'proveedor'."
        )


class CredencialesAccesoInvalidasError(Exception):
    """
    Excepcion de dominio: el código de petición no existe o el PIN no coincide.

    Se usa un único tipo de excepción para ambos casos (código no encontrado y PIN
    incorrecto) con el fin de no revelar cuál de las dos condiciones falló y así
    prevenir ataques de enumeración de códigos de petición válidos.
    """

    def __init__(self) -> None:
        super().__init__("Código de petición o PIN incorrecto.")


class TokenDiligenciamientoInvalidoError(Exception):
    """El token nunca existió en el sistema."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__("El enlace de diligenciamiento no es válido.")


class TokenConsumidoError(Exception):
    """
    El token existió y fue consumido: el formulario asociado ya fue enviado.

    Semánticamente distinto de TokenDiligenciamientoInvalidoError (token nunca existió).
    Aquí el token fue válido y usado — el recurso está 'gone' (HTTP 410), no 'not found' (HTTP 404).
    Esto permite al frontend diferenciar "link inválido" de "formulario ya completado"
    y mostrar el mensaje apropiado en cada caso.
    """

    def __init__(self) -> None:
        super().__init__("Este formulario ya fue completado y no puede ser modificado.")


class FirmaNoDisponibleError(Exception):
    """
    El documento firmado no está disponible: el formulario no ha sido firmado
    o el archivo no existe en disco.
    """

    def __init__(self, formulario_id: str) -> None:
        self.formulario_id = formulario_id
        super().__init__(
            f"El documento firmado del formulario '{formulario_id}' no está disponible."
        )


class AccesoExpiradoError(Exception):
    """
    Excepcion de dominio: el AccesoManual superó su fecha de vigencia.

    Se distingue de TokenDiligenciamientoInvalidoError (token nunca existió)
    y de CredencialesAccesoInvalidasError (PIN incorrecto): aquí las credenciales
    existieron y eran correctas, pero el plazo de 5 días hábiles ya venció.
    """

    def __init__(self) -> None:
        super().__init__("El acceso ha expirado. Solicite un nuevo enlace al área responsable.")


class SinPermisoError(Exception):
    """El usuario autenticado no tiene rol para acceder a este recurso."""

    def __init__(self, tipo_contraparte: str) -> None:
        super().__init__(f"Sin acceso a la carpeta '{tipo_contraparte.upper()}'.")


class WebhookTokenInvalidoError(Exception):
    """
    El secret_token recibido en el webhook de ZohoSign no coincide con el configurado.

    Usar esta excepción en lugar de PermissionError (built-in de Python para errores
    de sistema de archivos) evita que errores reales de permisos en disco sean
    silenciosamente capturados como HTTP 403.
    """

    def __init__(self) -> None:
        super().__init__("Token de webhook inválido.")


class CorreoDestinatarioNoRegistradoError(Exception):
    """
    Excepcion de dominio: el destinatario no ha registrado su correo electrónico.

    Ocurre cuando se intenta realizar operaciones que REQUIEREN un correo válido
    (envío del formulario, firma electrónica, notificaciones) pero el destinatario
    aún no ha completado el paso de captura de correo. Esta es una validación
    crítica de negocio que debe bloquearse en todos los puntos de entrada.

    Es diferente de FormularioNoEditableError: aquí el problema es específicamente
    la falta de correo, no el estado general del formulario.
    """

    def __init__(self, formulario_id: str) -> None:
        self.formulario_id = formulario_id
        super().__init__(
            f"Destinatario sin correo registrado para formulario '{formulario_id}'. "
            "Debe completar el paso de captura de correo antes de enviar."
        )

class AccesoActivoExistenteError(Exception):
    def __init__(self, acceso_id: str) -> None:
        self.acceso_id = acceso_id
        super().__init__("Ya existe un acceso activo para este correo electrónico.")

class FrecuenciaEnvioExcedidaError(Exception):
    def __init__(self, segundos_restantes: int) -> None:
        self.segundos_restantes = segundos_restantes
        super().__init__(f"Debe esperar {segundos_restantes} segundos antes de solicitar otro correo.")
