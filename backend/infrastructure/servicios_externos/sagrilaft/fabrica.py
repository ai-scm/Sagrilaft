from domain.puertos.consultor_listas_cautela import ConsultorListasCautela
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.servicios_externos.sagrilaft.dummy import ConsultorListasCautelaDummy
from infrastructure.servicios_externos.sagrilaft.real import ConsultorListasCautelaAPI
from infrastructure.servicios_externos.sagrilaft.deshabilitado import ConsultorListasCautelaDeshabilitado

# Valores válidos de PROVEEDOR_LISTAS_CAUTELA. Únicos en todo el backend para
# que ni la fábrica ni los routers vuelvan a hardcodear el string suelto.
PROVEEDOR_DUMMY = "dummy"
PROVEEDOR_SAGRILAFT = "sagrilaft"
PROVEEDOR_DESHABILITADO = "deshabilitado"


def obtener_consultor_listas(config: SagrilaftListasConfig) -> ConsultorListasCautela:
    """Factory method para inyección de dependencias (Strategy).

    Recibe la configuración ya validada por `load_config()` — no lee
    variables de entorno directamente, para que `PROVEEDOR_LISTAS_CAUTELA`
    tenga una única fuente de verdad (AppConfig) en vez de quedar fuera de
    la validación de arranque de la aplicación.
    """
    if config.proveedor == PROVEEDOR_DESHABILITADO:
        return ConsultorListasCautelaDeshabilitado()
    elif config.proveedor == PROVEEDOR_SAGRILAFT:
        return ConsultorListasCautelaAPI(
            url_base=config.api_url,
            api_key=config.api_key,
        )

    # Por defecto 'dummy' para desarrollo local o si el valor no es reconocido
    return ConsultorListasCautelaDummy()
