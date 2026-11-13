"""Controles comunes F1. El contexto lo construye autenticación, nunca el cliente."""
from dataclasses import dataclass
from typing import Callable

from domain.listas.contratos import CrearConsultaV2, ContextoExpediente
from domain.listas.puertos import ListasNoDisponibles
from infrastructure.config.configuracion import SagrilaftListasConfig


# Roles propuestos: solo se interpretan tras validar la identidad. No se crean en Keycloak.
PERMISOS_POR_ROL = {
    "listas_operador": frozenset({"listas.consultar", "listas.ver_evidencias"}),
    "listas_revisor": frozenset({"listas.consultar", "listas.ver_evidencias", "listas.revisar"}),
    "listas_cargador": frozenset({"listas.importar", "listas.comparar", "listas.ver_administracion"}),
    "listas_aprobador": frozenset({"listas.comparar", "listas.ver_administracion", "listas.aprobar_version", "listas.activar_version"}),
    "listas_incidentes": frozenset({"listas.ver_administracion", "listas.bloquear_version", "listas.reconstruir_version"}),
    "listas_busqueda_independiente": frozenset({"listas.consultar_independiente", "listas.ver_evidencias"}),
}


class AccesoListasDenegado(PermissionError):
    pass


@dataclass(frozen=True)
class ActorListas:
    issuer: str
    sub: str
    permisos: frozenset[str]

    @classmethod
    def desde_identidad_validada(cls, issuer: str, sub: str, roles: tuple[str, ...]):
        """No valida JWT: la frontera de autenticación debe hacerlo antes (F3)."""
        permisos = frozenset(p for rol in roles for p in PERMISOS_POR_ROL.get(rol, ()))
        return cls(issuer, sub, permisos)

    def exigir(self, permiso: str) -> None:
        if not self.issuer.strip() or not self.sub.strip() or permiso not in self.permisos:
            raise AccesoListasDenegado("Identidad o permiso de listas no válido")


class PoliticaListasV2:
    def __init__(self, config: SagrilaftListasConfig, entorno: str):
        config.validar_entorno(entorno)
        self.config = config
        self.entorno = entorno

    def consulta(self, actor: ActorListas, solicitud: CrearConsultaV2,
                 puede_acceder_expediente: Callable[[ActorListas, str], bool]) -> None:
        if isinstance(solicitud.contexto, ContextoExpediente):
            actor.exigir("listas.consultar")
            if not puede_acceder_expediente(actor, solicitud.contexto.expediente_id):
                raise AccesoListasDenegado("Sin acceso al expediente")
        else:
            actor.exigir("listas.consultar_independiente")
            if not self.config.independiente_habilitada:
                raise ListasNoDisponibles("Búsqueda independiente deshabilitada")
        if self.config.implementacion == "deshabilitado":
            raise ListasNoDisponibles("Consultas deshabilitadas")

    def evidencia(self, actor: ActorListas, evidencia_id: str,
                  puede_acceder: Callable[[ActorListas, str], bool]) -> None:
        actor.exigir("listas.ver_evidencias")
        if not puede_acceder(actor, evidencia_id):
            raise AccesoListasDenegado("Sin acceso a la evidencia")
        # El selector de consultas no bloquea el historial autorizado.

    def administracion(self, actor: ActorListas, operacion: str) -> None:
        permisos = {
            "cargar": "listas.importar", "comparar": "listas.comparar",
            "aprobar": "listas.aprobar_version", "activar": "listas.activar_version",
            "revertir": "listas.activar_version", "bloquear": "listas.bloquear_version",
            "reconstruir": "listas.reconstruir_version", "ver": "listas.ver_administracion",
        }
        if operacion not in permisos:
            raise AccesoListasDenegado("Operación administrativa desconocida")
        actor.exigir(permisos[operacion])
        if not self.config.admin_habilitada:
            raise ListasNoDisponibles("Administración deshabilitada")

    def aprobar(self, actor: ActorListas, cargador: ActorListas) -> None:
        self.administracion(actor, "aprobar")
        if not cargador.issuer.strip() or not cargador.sub.strip():
            raise AccesoListasDenegado("Origen de carga no verificable")
        # F2 comprobará comparación vigente/aprobación bajo transacción.
