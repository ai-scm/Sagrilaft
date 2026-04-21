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


class FormularioNoEncontradoPorCredencialesError(Exception):
    """Excepcion de dominio: no existe un formulario borrador para las credenciales dadas."""

    def __init__(self, correo: str, numero_identificacion: str) -> None:
        self.correo = correo
        self.numero_identificacion = numero_identificacion
        super().__init__("No se encontró ningún formulario con esas credenciales.")


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
