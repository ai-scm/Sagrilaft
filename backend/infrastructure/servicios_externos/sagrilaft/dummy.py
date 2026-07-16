import time
from datetime import datetime
from domain.puertos.consultor_listas_cautela import (
    ConsultorListasCautela,
    CriterioConsultaListas,
    ResultadoConsultaListas,
    ErrorConsultaListas
)

class ConsultorListasCautelaDummy(ConsultorListasCautela):
    def consultar(self, criterio: CriterioConsultaListas) -> ResultadoConsultaListas:
        # Simulamos el tiempo de espera (latencia de red/procesamiento)
        time.sleep(2)
        
        self._validar_criterio(criterio)
        return self._simular_respuesta(criterio)

    def _validar_criterio(self, criterio: CriterioConsultaListas) -> None:
        if not criterio.numero_identificacion:
            raise ErrorConsultaListas("El número de identificación es requerido")

    def _simular_respuesta(self, criterio: CriterioConsultaListas) -> ResultadoConsultaListas:
        # Simulador de escenarios basado en prefijos de identificación
        prefix = criterio.numero_identificacion[:3]
        
        if prefix == "999":
            return self._resultado_encontrado(
                "ALTO", 
                "[ALTOS] Fuente: Listas y PEPS (Código: ofac_lista_clinton). Se encontró coincidencia en listas internacionales restrictivas. | "
                "[MEDIOS] Fuente: Policía Nacional (Código: policia). Presenta anotaciones vigentes."
            )
        if prefix == "888":
            return self._resultado_encontrado(
                "MEDIO", 
                "[MEDIOS] Fuente: RUES (Código: rues_estado). La matrícula mercantil se encuentra inactiva."
            )
        if prefix == "777":
            return self._resultado_encontrado(
                "BAJO", 
                "[BAJOS] Fuente: SIMIT (Código: simit). Posee 2 multas de tránsito pendientes de pago."
            )
        if prefix == "000":
            raise ErrorConsultaListas("Error simulado de conexión con el proveedor Tusdatos.co (Timeout).")
        
        return self._resultado_limpio()

    def _resultado_limpio(self) -> ResultadoConsultaListas:
        return ResultadoConsultaListas(
            encontrado=False,
            nivel_riesgo="NINGUNO",
            fecha_consulta=datetime.utcnow().isoformat(),
            reporte_id="dummy_limpio_123"
        )

    def _resultado_encontrado(self, riesgo: str, detalle: str) -> ResultadoConsultaListas:
        return ResultadoConsultaListas(
            encontrado=True,
            nivel_riesgo=riesgo,
            detalles=detalle,
            fecha_consulta=datetime.utcnow().isoformat(),
            reporte_id="dummy_hallazgo_456"
        )

    def descargar_pdf(self, reporte_id: str) -> bytes:
        # Simulamos la descarga de un PDF real retornando un archivo PDF estructuralmente válido pero mínimo
        if not reporte_id:
            raise ErrorConsultaListas("ID de reporte inválido.")
        # Minimal PDF
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n198\n%%EOF"
