"""Equivalencias de calidad del paquete Advanced revisado; no decide coincidencias."""
from domain.listas.catalogos_busqueda import CatalogoCalidadFuente, EquivalenciaCalidad

CALIDADES_OFAC_ADVANCED = CatalogoCalidadFuente(
    fuente_codigo="ofac_sdn", version="ofac-advanced-calidad-v1",
    equivalencias=(
        EquivalenciaCalidad(codigo_original="1560", calidad="CONFIRMADO"),
        EquivalenciaCalidad(codigo_original="1561", calidad="FALSO"),
        EquivalenciaCalidad(codigo_original="91479", calidad="REPORTADO"),
        EquivalenciaCalidad(codigo_original="1", calidad="DESCONOCIDO"),
    ),
)
