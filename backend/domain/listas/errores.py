"""Errores de negocio de almacenamiento e historial; no ocultan errores SQL."""


class ConflictoListas(RuntimeError):
    pass


class VersionNoDisponible(ConflictoListas):
    pass


class TrabajoNoVigente(ConflictoListas):
    pass


class ErrorIntegridadEvidencia(RuntimeError):
    pass
