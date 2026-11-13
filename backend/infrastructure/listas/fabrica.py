"""Fábrica v2: adaptadores no implementados nunca se sustituyen por simulación."""
from domain.listas.puertos import ConsultorListasV2, ListasNoDisponibles
from infrastructure.config.configuracion import SagrilaftListasConfig
from infrastructure.listas.simulado import SimuladorListasV2


def crear_consultor_v2(config: SagrilaftListasConfig, entorno: str) -> ConsultorListasV2:
    config.validar_entorno(entorno)
    if config.implementacion == "simulado":
        return SimuladorListasV2(config.escenario)
    if config.implementacion == "deshabilitado":
        raise ListasNoDisponibles("Consultas deshabilitadas")
    if config.implementacion in {"archivos", "externo"}:
        raise ListasNoDisponibles(f"Adaptador {config.implementacion} v2 pendiente de implementación")
    raise ValueError("Implementación desconocida")


def crear_consultor_archivos_local(sesiones, politica, custodia, entorno, manifiesto, coberturas):
    if entorno not in {"development", "test"}:
        raise ListasNoDisponibles("El adaptador archivos 2.1 solo está habilitado para ensayo local")
    from infrastructure.listas.consultor_archivos import ConsultorArchivos
    return ConsultorArchivos(sesiones, politica, custodia, manifiesto, coberturas)
