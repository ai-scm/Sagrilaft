from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel

class CriterioConsultaListas(BaseModel):
    tipo_identificacion: str
    numero_identificacion: str
    nombre_completo: str
    fecha_expedicion: Optional[str] = None

class ResultadoConsultaListas(BaseModel):
    encontrado: bool
    nivel_riesgo: str  # ALTO, MEDIO, BAJO, NINGUNO
    detalles: Optional[str] = None
    fecha_consulta: str
    reporte_id: Optional[str] = None  # ID del reporte en el proveedor para descargar PDFs

class ErrorConsultaListas(Exception):
    """Excepción base para errores en la consulta de listas cautela."""
    pass

class ConsultorListasCautela(ABC):
    @abstractmethod
    def consultar(self, criterio: CriterioConsultaListas) -> ResultadoConsultaListas:
        """
        Consulta una persona o entidad en las bases de datos de listas cautela.
        """
        pass

    @abstractmethod
    def descargar_pdf(self, reporte_id: str) -> bytes:
        """
        Descarga el reporte detallado en formato PDF basado en su ID del proveedor.
        """
        pass
