"""
Tipos de dominio del formulario SAGRILAFT.

Enums que representan conceptos del negocio. No dependen de ningún framework,
ORM ni biblioteca externa — solo de la biblioteca estándar de Python.
"""

import enum


class EstadoFormulario(str, enum.Enum):
    BORRADOR        = "borrador"
    ENVIADO         = "enviado"
    EN_CORRECCION   = "en_correccion"
    VALIDADO        = "validado"
    RECHAZADO       = "rechazado"
    PENDIENTE_FIRMA = "pendiente_firma"
    FIRMADO         = "firmado"
    CERRADO         = "cerrado"


class TipoPersona(str, enum.Enum):
    JURIDICA = "juridica"
    NATURAL  = "natural"


class TipoContraparte(str, enum.Enum):
    PROVEEDOR = "proveedor"
    CLIENTE   = "cliente"


class TipoSolicitud(str, enum.Enum):
    VINCULACION  = "vinculacion"
    ACTUALIZACION = "actualizacion"


class ClasificacionActividad(str, enum.Enum):
    """
    Clasificación de la actividad comercial de la contraparte
    según su rol en la cadena de valor del sector regulado.
    """
    COMERCIALIZADOR = "C"
    DISTRIBUIDOR    = "D"
    REPRESENTANTE   = "R"
    FABRICANTE      = "F"
    IMPORTADOR      = "I"


class ActividadClasificacion(str, enum.Enum):
    """Actividad principal de la empresa (Sección 8)."""
    INDUSTRIAL         = "Industrial"
    COMERCIAL          = "Comercial"
    FINANCIERA         = "Financiera"
    ECONOMIA_SOLIDARIA = "Economia solidaria"
    OTRA               = "Otra"


class SectorEmpresa(str, enum.Enum):
    """
    Sector de la empresa (Sección 8).

    Valores canónicos: "Público", "Privado", "Mixto".
    """
    PUBLICO = "Público"
    PRIVADO = "Privado"
    MIXTO   = "Mixto"


class ResponsabilidadRenta(str, enum.Enum):
    """
    Responsabilidad del contribuyente frente al impuesto sobre la renta (Sección 8).
    """
    DECLARANTE                  = "Declarante"
    NO_DECLARANTE               = "No declarante"
    DECLARANTE_REGIMEN_ESPECIAL = "Declarante Regimen Especial"


class ResponsabilidadIva(str, enum.Enum):
    """Responsabilidad del contribuyente frente al IVA (Sección 8)."""
    RESPONSABLE    = "Responsable"
    NO_RESPONSABLE = "No responsable"


class RegimenIva(str, enum.Enum):
    """Régimen de IVA al que pertenece el contribuyente (Sección 8)."""
    REGIMEN_COMUN        = "Régimen común"
    REGIMEN_SIMPLIFICADO = "Régimen simplificado"
    NINGUN_REGIMEN       = "Ningún régimen"


class AreaResponsable(str, enum.Enum):
    """Área interna responsable de gestionar el acceso manual al formulario SAGRILAFT."""
    VENTAS   = "ventas"
    LEGAL    = "legal"
    FINANZAS = "finanzas"
    RECURSOS_HUMANOS = "recursos_humanos"

