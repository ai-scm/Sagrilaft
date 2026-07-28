from domain.puertos.consultor_listas_cautela import ConsultorListasCautela
from infrastructure.configuracion import SagrilaftListasConfig
from infrastructure.servicios_externos.sagrilaft.dummy import ConsultorListasCautelaDummy
from infrastructure.servicios_externos.sagrilaft.real import ConsultorListasCautelaAPI
from infrastructure.servicios_externos.sagrilaft.deshabilitado import ConsultorListasCautelaDeshabilitado


def obtener_consultor_listas(config: SagrilaftListasConfig) -> ConsultorListasCautela:
    """Factory method para inyección de dependencias (Strategy).

    Recibe la configuración ya validada por `load_config()` — no lee
    variables de entorno directamente, para que `PROVEEDOR_LISTAS_CAUTELA`
    tenga una única fuente de verdad (AppConfig) en vez de quedar fuera de
    la validación de arranque de la aplicación.
    """
    if config.proveedor == "deshabilitado":
        return ConsultorListasCautelaDeshabilitado()
    elif config.proveedor == "sagrilaft":
        return ConsultorListasCautelaAPI(
            url_base=config.api_url,
            api_key=config.api_key,
        )

    # Por defecto 'dummy' para desarrollo local o si el valor no es reconocido
    return ConsultorListasCautelaDummy()
