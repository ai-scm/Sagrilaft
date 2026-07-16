from datetime import datetime
from domain.puertos.consultor_listas_cautela import (
    ConsultorListasCautela,
    CriterioConsultaListas,
    ResultadoConsultaListas
)

class ConsultorListasCautelaDeshabilitado(ConsultorListasCautela):
    def consultar(self, criterio: CriterioConsultaListas) -> ResultadoConsultaListas:
        # Retorna siempre una aprobación automática sin realizar consultas (Null Object)
        return ResultadoConsultaListas(
            encontrado=False,
            nivel_riesgo="NINGUNO",
            detalles="Consulta omitida: Servicio deshabilitado por configuración.",
            fecha_consulta=datetime.utcnow().isoformat(),
            reporte_id=None
        )

    def descargar_pdf(self, reporte_id: str) -> bytes:
        raise ErrorConsultaListas("El servicio SAGRILAFT está deshabilitado. No se pueden generar evidencias PDF.")
