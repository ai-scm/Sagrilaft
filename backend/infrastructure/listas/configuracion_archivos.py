"""Configuración explícita del ensayo local; no consulta configuración remota."""
from dataclasses import dataclass
import os
from uuid import UUID

from domain.listas.puertos import ListasNoDisponibles


@dataclass(frozen=True)
class ConfiguracionArchivosLocal:
    fuentes: tuple[str, ...]
    politica_id: UUID

    @classmethod
    def cargar(cls, entorno):
        if entorno not in {"development", "test"} or os.getenv("LISTAS_ARCHIVOS_LOCAL_HABILITADA") != "true":
            raise ListasNoDisponibles("Las consultas por archivos requieren habilitación local explícita")
        fuentes = tuple(c.strip() for c in os.getenv("LISTAS_ARCHIVOS_FUENTES", "").split(",") if c.strip())
        try:
            politica = UUID(os.environ["LISTAS_ARCHIVOS_POLITICA_ID"])
        except (KeyError, ValueError) as error:
            raise ListasNoDisponibles("Falta la política registrada para el ensayo local") from error
        if not fuentes or len(set(fuentes)) != len(fuentes):
            raise ListasNoDisponibles("Se requieren fuentes explícitas, sin duplicados")
        return cls(fuentes, politica)
