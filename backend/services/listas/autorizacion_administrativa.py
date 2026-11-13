"""Reglas puras F5.1; las identidades deben provenir de JWT y registros confiables."""
from domain.listas.administracion import TipoOperacion
from services.listas.politica_v2 import ActorListas


def misma_persona(primero: ActorListas, segundo: ActorListas) -> bool:
    return (primero.issuer, primero.sub) == (segundo.issuer, segundo.sub)


def exigir_revision(actor: ActorListas, solicitante: ActorListas,
                    cargador: ActorListas, tipo: TipoOperacion) -> None:
    actor.exigir("listas.aprobar_version")
    if tipo not in {"ACTIVACION", "REVERSION"}:
        raise ValueError("Operación administrativa desconocida")
    identidades_requeridas = (solicitante, cargador) if tipo == "ACTIVACION" else (solicitante,)
    if any(not identidad.issuer.strip() or not identidad.sub.strip()
           for identidad in identidades_requeridas):
        raise PermissionError("Identidad de origen no verificable")



def exigir_ejecucion(actor: ActorListas, aprobador: ActorListas,
                     solicitante: ActorListas, cargador: ActorListas, tipo: TipoOperacion) -> None:
    exigir_revision(actor, solicitante, cargador, tipo)
    actor.exigir("listas.activar_version")
    if not misma_persona(actor, aprobador):
        raise PermissionError("Debe ejecutar quien revisó y aprobó la operación")


def exigir_entorno_sintetico(entorno: str) -> None:
    if entorno not in {"test", "local", "development"}:
        raise PermissionError("El perfil sintético solo está disponible en local")
