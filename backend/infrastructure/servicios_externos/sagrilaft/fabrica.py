import os
from domain.puertos.consultor_listas_cautela import ConsultorListasCautela
from infrastructure.servicios_externos.sagrilaft.dummy import ConsultorListasCautelaDummy
from infrastructure.servicios_externos.sagrilaft.real import ConsultorListasCautelaAPI
from infrastructure.servicios_externos.sagrilaft.deshabilitado import ConsultorListasCautelaDeshabilitado

class ConfigIntegracionSagrilaft:
    @property
    def proveedor(self) -> str:
        # Feature flag estratégico: 'dummy' | 'sagrilaft' | 'deshabilitado'
        return os.getenv("PROVEEDOR_LISTAS_CAUTELA", "dummy").lower()

def obtener_consultor_listas() -> ConsultorListasCautela:
    """Factory method para inyección de dependencias (Strategy)."""
    config = ConfigIntegracionSagrilaft()
    proveedor = config.proveedor
    
    if proveedor == "deshabilitado":
        return ConsultorListasCautelaDeshabilitado()
    elif proveedor == "sagrilaft":
        return ConsultorListasCautelaAPI(
            url_base=os.getenv("SAGRILAFT_API_URL", ""),
            api_key=os.getenv("SAGRILAFT_API_KEY", "")
        )
    
    # Por defecto 'dummy' para desarrollo local o si el valor no es reconocido
    return ConsultorListasCautelaDummy()
