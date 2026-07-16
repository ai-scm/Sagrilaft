from typing import Dict, Any, Optional, List
from domain.puertos.consultor_listas_cautela import (
    ConsultorListasCautela, 
    CriterioConsultaListas,
    ErrorConsultaListas
)
from domain.puertos.repositorios import RepositorioExpediente
from domain.excepciones import FormularioNoEncontradoError, SinPermisoError
from domain.formulario.tipos import EstadoFormulario

class ServicioVerificacionSagrilaft:
    def __init__(self, consultor: ConsultorListasCautela, repo: RepositorioExpediente):
        self._consultor = consultor
        self._repo = repo

    def verificar_contraparte(self, formulario_id: str, contrapartes_permitidas: Optional[List[str]] = None, datos_manuales: Optional[Any] = None) -> dict:
        """Ejecuta la validación de listas cautela para un formulario."""
        
        # Obtenemos el formulario verificando que esté en un estado válido y tengamos permisos
        formulario = self._repo.obtener(formulario_id, [
            EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO, 
            EstadoFormulario.PENDIENTE_FIRMA, EstadoFormulario.FIRMADO,
            EstadoFormulario.RECHAZADO, EstadoFormulario.CERRADO
        ])
        
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
            
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)

        if datos_manuales:
            criterio = CriterioConsultaListas(
                tipo_identificacion=datos_manuales.tipo_identificacion,
                numero_identificacion=datos_manuales.numero_identificacion,
                nombre_completo=datos_manuales.nombre_completo,
                fecha_expedicion=datos_manuales.fecha_expedicion
            )
        else:
            criterio = CriterioConsultaListas(
                tipo_identificacion=formulario.tipo_identificacion or "",
                numero_identificacion=formulario.numero_identificacion or "",
                nombre_completo=formulario.razon_social or "Sin Nombre",
                fecha_expedicion=None # Por ahora el formulario de BD no tiene este campo
            )
        
        try:
            resultado = self._consultor.consultar(criterio)
            
            # Persistir el ID del reporte para descargar PDFs en el futuro
            if resultado.reporte_id:
                self._repo.actualizar_sagrilaft_reporte_id(formulario_id, resultado.reporte_id)
            
            if resultado.encontrado:
                return {
                    "estado": "RECHAZADO_SAGRILAFT", 
                    "riesgo": resultado.nivel_riesgo,
                    "detalles": resultado.detalles,
                    "fecha_consulta": resultado.fecha_consulta
                }
            
            return {
                "estado": "APROBADO_SAGRILAFT",
                "fecha_consulta": resultado.fecha_consulta,
                "detalles": resultado.detalles
            }
        except ErrorConsultaListas as error:
            return {"estado": "ERROR_VERIFICACION", "mensaje": str(error)}

    def descargar_certificado_sagrilaft(self, formulario_id: str, contrapartes_permitidas: Optional[List[str]] = None) -> bytes:
        """
        Descarga el certificado PDF desde el proveedor usando el ID guardado en el expediente.
        """
        formulario = self._repo.obtener(formulario_id, [
            EstadoFormulario.ENVIADO, EstadoFormulario.VALIDADO, 
            EstadoFormulario.PENDIENTE_FIRMA, EstadoFormulario.FIRMADO,
            EstadoFormulario.RECHAZADO
        ])
        
        if not formulario:
            raise FormularioNoEncontradoError(formulario_id)
            
        if contrapartes_permitidas is not None and formulario.tipo_contraparte not in contrapartes_permitidas:
            raise SinPermisoError(formulario.tipo_contraparte)
            
        if not formulario.sagrilaft_reporte_id:
            raise ValueError("El formulario no tiene un certificado SAGRILAFT asociado.")
            
        return self._consultor.descargar_pdf(formulario.sagrilaft_reporte_id)
