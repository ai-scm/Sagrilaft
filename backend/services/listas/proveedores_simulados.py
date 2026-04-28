"""
Proveedores simulados de listas de cautela.

Cada clase implementa ProveedorListaCautelaImp usando datos en memoria.
En producción, reemplazar (o complementar) con proveedores reales que
consuman las APIs/servicios oficiales indicados en cada clase.

OCP : agregar un nuevo proveedor solo requiere instanciar _ProveedorSimuladoBase
      con sus datos — sin modificar la lógica de búsqueda.
DRY : _ProveedorSimuladoBase centraliza la normalización y comparación
      que antes se repetía en cada clase proveedora.
"""

from typing import List, Optional

from api.schemas import ResultadoListaCautela
from services.listas.protocolo_listas import ProveedorListaCautelaImp
from services.utils.texto import quitar_diacriticos


# ─── Datos simulados ─────────────────────────────────────────────────────────

_REGISTROS_OFAC: List[str] = [
    "juan pablo escobar",
    "carlos lehder",
    "gonzalo rodriguez gacha",
]

_REGISTROS_ONU: List[str] = [
    "osama bin laden",
    "ayman al zawahiri",
]

_REGISTROS_PROCURADURIA: List[str] = [
    "funcionario ejemplo sancionado",
]


# ─── Infraestructura de búsqueda ─────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """
    Normaliza texto para comparación: minúsculas, sin espacios extremos
    y sin diacríticos (tildes, ñ→n, ü→u, etc.).

    Evita falsos negativos al comparar nombres con y sin tilde.
    """
    return quitar_diacriticos(texto).lower().strip()


class _ProveedorSimuladoBase:
    """
    Base reutilizable para proveedores simulados de listas de cautela.

    SRP : concentra la lógica de búsqueda por coincidencia parcial normalizada.
    OCP : las subclases solo declaran nombre y registros; esta lógica no cambia.
    """

    def __init__(self, nombre: str, registros: List[str]) -> None:
        self.nombre = nombre
        self._registros = registros

    def buscar(
        self,
        nombre: str,
        numero_identificacion: Optional[str] = None,
    ) -> ResultadoListaCautela:
        """Busca por coincidencia parcial normalizada en los registros en memoria."""
        nombre_normalizado = _normalizar(nombre)

        for entrada in self._registros:
            entrada_normalizada = _normalizar(entrada)
            if nombre_normalizado in entrada_normalizada or entrada_normalizada in nombre_normalizado:
                return ResultadoListaCautela(
                    lista=self.nombre,
                    encontrado=True,
                    detalle=f"Coincidencia encontrada en {self.nombre}: '{entrada}'",
                    nivel_riesgo="alto",
                )

        return ResultadoListaCautela(
            lista=self.nombre,
            encontrado=False,
            detalle=f"Sin coincidencias en {self.nombre}",
            nivel_riesgo="bajo",
        )


# ─── Proveedores concretos ────────────────────────────────────────────────────

class ProveedorOfac(_ProveedorSimuladoBase):
    """
    Proveedor simulado para la lista SDN de la OFAC (EE.UU.).

    Producción: https://sanctionslistservice.ofac.treas.gov/api/search
    """

    def __init__(self) -> None:
        super().__init__("OFAC (EE.UU.)", _REGISTROS_OFAC)


class ProveedorOnu(_ProveedorSimuladoBase):
    """
    Proveedor simulado para la lista consolidada de sanciones de Naciones Unidas.

    Producción: https://scsanctions.un.org/api/
    """

    def __init__(self) -> None:
        super().__init__("Naciones Unidas", _REGISTROS_ONU)


class ProveedorProcuraduria(_ProveedorSimuladoBase):
    """
    Proveedor simulado para el registro de sancionados de la Procuraduría
    General de la Nación (Colombia).

    Producción: https://siri.procuraduria.gov.co o https://www.datos.gov.co/
    """

    def __init__(self) -> None:
        super().__init__("Procuraduría General de la Nación", _REGISTROS_PROCURADURIA)


class ProveedorContraloria(_ProveedorSimuladoBase):
    """
    Proveedor simulado para el Boletín de Responsables Fiscales de la
    Contraloría General de la República (Colombia).

    Producción: https://www.contraloria.gov.co/web/guest/boletin-de-responsables-fiscales
    Sin registros en memoria — siempre retorna sin coincidencias.
    """

    def __init__(self) -> None:
        super().__init__("Contraloría General de la República", [])


class ProveedorPoliciaAntecedentes(_ProveedorSimuladoBase):
    """
    Proveedor simulado para la base de antecedentes de la Policía Nacional
    de Colombia.

    Producción: https://antecedentes.policia.gov.co:7005/WebJudicial/
    Sin registros en memoria — siempre retorna sin coincidencias.
    """

    def __init__(self) -> None:
        super().__init__("Policía Nacional (Antecedentes)", [])


# ─── Registro de proveedores por defecto ─────────────────────────────────────

PROVEEDORES_SIMULADOS: List[ProveedorListaCautelaImp] = [
    ProveedorOfac(),
    ProveedorOnu(),
    ProveedorProcuraduria(),
    ProveedorContraloria(),
    ProveedorPoliciaAntecedentes(),
]
