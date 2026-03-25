"""
Proveedores mock de listas de cautela.

Cada clase implementa IListaCautelaProvider usando datos en memoria.
En producción, reemplazar (o complementar) con providers reales que
consuman las APIs/servicios oficiales indicados en cada clase.
"""
from typing import Optional

from schemas import ResultadoListaCautela

# ---------------------------------------------------------------------------
# Datos mock
# ---------------------------------------------------------------------------
_MOCK_OFAC = ["juan pablo escobar", "carlos lehder", "gonzalo rodriguez gacha"]
_MOCK_ONU = ["osama bin laden", "ayman al zawahiri"]
_MOCK_PROCURADURIA = ["funcionario ejemplo sancionado"]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------
def _normalizar(texto: str) -> str:
    """Normaliza texto a minúsculas sin espacios extremos."""
    return texto.lower().strip()


def _buscar_en_lista(
    nombre: str,
    lista: list[str],
    nombre_lista: str,
) -> ResultadoListaCautela:
    """Busca nombre en una lista de strings y retorna ResultadoListaCautela."""
    nombre_norm = _normalizar(nombre)
    for entrada in lista:
        if nombre_norm in entrada or entrada in nombre_norm:
            return ResultadoListaCautela(
                lista=nombre_lista,
                encontrado=True,
                detalle=f"Coincidencia encontrada en {nombre_lista}: '{entrada}'",
                nivel_riesgo="alto",
            )
    return ResultadoListaCautela(
        lista=nombre_lista,
        encontrado=False,
        detalle=f"Sin coincidencias en {nombre_lista}",
        nivel_riesgo="bajo",
    )


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class MockOfacProvider:
    """
    Provider mock para la lista SDN de la OFAC (EE.UU.).

    Producción: consumir https://sanctionslistservice.ofac.treas.gov/api/search
    mediante petición HTTP con el nombre/id como parámetros de query.
    """

    nombre: str = "OFAC (EE.UU.)"

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        return _buscar_en_lista(nombre, _MOCK_OFAC, self.nombre)


class MockOnuProvider:
    """
    Provider mock para la lista consolidada de sanciones de Naciones Unidas.

    Producción: consumir https://scsanctions.un.org/resources/xml/en/consolidated.xml
    o la API REST disponible en https://scsanctions.un.org/api/.
    """

    nombre: str = "Naciones Unidas"

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        return _buscar_en_lista(nombre, _MOCK_ONU, self.nombre)


class MockProcuraduriaProvider:
    """
    Provider mock para el registro de sancionados de la Procuraduría General de la Nación (Colombia).

    Producción: consumir el servicio web de consulta SIRI disponible en
    https://siri.procuraduria.gov.co/pgn.consultasanciones/Consulta.aspx
    o el servicio de datos abiertos en https://www.datos.gov.co/.
    """

    nombre: str = "Procuraduría General de la Nación"

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        return _buscar_en_lista(nombre, _MOCK_PROCURADURIA, self.nombre)


class MockContraloriaProvider:
    """
    Provider mock para el boletín de responsables fiscales de la Contraloría General de la República (Colombia).

    Producción: consumir la API del Boletín de Responsables Fiscales (BRF) disponible en
    https://www.contraloria.gov.co/web/guest/boletin-de-responsables-fiscales
    o el servicio REST del portal de datos abiertos.

    Sin datos mock por ahora — siempre retorna sin coincidencias.
    """

    nombre: str = "Contraloría General de la República"

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        return ResultadoListaCautela(
            lista=self.nombre,
            encontrado=False,
            detalle=f"Sin coincidencias en {self.nombre}",
            nivel_riesgo="bajo",
        )


class MockPoliciaNacionalProvider:
    """
    Provider mock para la base de antecedentes de la Policía Nacional de Colombia.

    Producción: consumir el servicio de certificados judiciales de la Policía Nacional
    disponible en https://antecedentes.policia.gov.co:7005/WebJudicial/
    mediante scraping autorizado o convenio institucional de acceso a API.

    Sin datos mock por ahora — siempre retorna sin coincidencias.
    """

    nombre: str = "Policía Nacional (Antecedentes)"

    def buscar(
        self,
        nombre: str,
        numero_id: Optional[str] = None,
    ) -> ResultadoListaCautela:
        return ResultadoListaCautela(
            lista=self.nombre,
            encontrado=False,
            detalle=f"Sin coincidencias en base de antecedentes",
            nivel_riesgo="bajo",
        )


# ---------------------------------------------------------------------------
# Lista de providers registrados por defecto
# ---------------------------------------------------------------------------
MOCK_PROVIDERS: list = [
    MockOfacProvider(),
    MockOnuProvider(),
    MockProcuraduriaProvider(),
    MockContraloriaProvider(),
    MockPoliciaNacionalProvider(),
]
