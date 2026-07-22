import time
import httpx
from datetime import datetime
from domain.puertos.consultor_listas_cautela import (
    ConsultorListasCautela,
    CriterioConsultaListas,
    ResultadoConsultaListas,
    ErrorConsultaListas
)
from infrastructure.emf_logger import emitir_metrica_emf

class ConsultorListasCautelaAPI(ConsultorListasCautela):
    def __init__(self, url_base: str, api_key: str):
        self._url_base = url_base.rstrip("/")
        # Tusdatos usa HTTPBasic Auth. Asumimos que api_key viene como "usuario:contraseña"
        self._auth = tuple(api_key.split(":", 1)) if ":" in api_key else None

    def consultar(self, criterio: CriterioConsultaListas) -> ResultadoConsultaListas:
        """
        Ejecuta el flujo completo de la API.
        Paso 1: Launch
        Paso 2: Polling (Job Status)
        Paso 3: Obtener Json (Hallazgos)
        """
        start_time = time.time()
        exito = True
        try:
            # PASO 1: Iniciar la consulta
            job_id = self._lanzar_consulta(criterio)
            
            # PASO 2: Esperar resultado (Polling)
            reporte_id, riesgo_maximo = self._consultar_estado(job_id)
            
            if riesgo_maximo != "NINGUNO":
                # PASO 3: Obtener Json (Hallazgos) y mapearlo al dominio
                return self._obtener_reporte_json(reporte_id, riesgo_maximo)
                
            return ResultadoConsultaListas(
                encontrado=False,
                nivel_riesgo="NINGUNO",
                fecha_consulta=datetime.utcnow().isoformat(),
                reporte_id=reporte_id
            )
        except Exception:
            exito = False
            raise
        finally:
            latencia_ms = int((time.time() - start_time) * 1000)
            emitir_metrica_emf(
                namespace="Sagrilaft/Negocio",
                dimensiones={"Servicio": "TusDatos", "Operacion": "ConsultaCompleta"},
                metricas={
                    "TusDatosLatency": latencia_ms,
                    "TusDatosSuccess": 1 if exito else 0,
                    "TusDatosError": 0 if exito else 1
                }
            )

    def _lanzar_consulta(self, criterio: CriterioConsultaListas) -> str:
        """Realiza el POST a /api/launch y retorna el jobid."""
        url = f"{self._url_base}/api/launch"
        
        # Mapear el tipo de documento del portal interno al formato de Tusdatos
        tipo_doc = criterio.tipo_identificacion.upper()
        
        payload = {
            "doc": str(criterio.numero_identificacion).replace(".", "").replace(",", "").replace("-", "").strip(),
            "typedoc": tipo_doc
        }
        
        # Según la doc, INT y PP requieren el nombre
        if tipo_doc in ["INT", "PP"]:
            payload["name"] = criterio.nombre_completo
        # NOMBRE requiere "nombre" en lugar de "doc"
        if tipo_doc == "NOMBRE":
            payload.pop("doc", None)
            payload["nombre"] = criterio.nombre_completo
            
        # CE y PPT requieren fecha de expedición
        if tipo_doc in ["CE", "PPT"] and criterio.fecha_expedicion:
            payload["fechaE"] = criterio.fecha_expedicion
        # También la enviamos si el usuario la digitó explícitamente para otro documento
        elif criterio.fecha_expedicion:
            payload["fechaE"] = criterio.fecha_expedicion

        try:
            # Usamos un cliente síncrono por ahora
            with httpx.Client(auth=self._auth) as client:
                response = client.post(url, json=payload, timeout=10.0)
                
                # Manejo específico del 403 (Habeas Data)
                if response.status_code == 403:
                    raise ErrorConsultaListas("Consulta bloqueada por protección de datos del titular (Habeas Data).")
                
                # Manejo genérico de errores 422, 500, etc.
                response.raise_for_status()
                data = response.json()
                
                job_id = data.get("jobid")
                if not job_id:
                    raise ErrorConsultaListas("La API no retornó el identificador de tarea (jobid).")
                    
                return job_id
                
        except httpx.HTTPStatusError as e:
            raise ErrorConsultaListas(f"El proveedor retornó error {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise ErrorConsultaListas(f"No se pudo conectar con el proveedor: {str(e)}")

    def _consultar_estado(self, job_id: str) -> tuple[str | None, str]:
        """
        Paso 2: Realiza polling al endpoint /api/results/{job_id} hasta que finalice.
        Retorna (reporte_id, riesgo_maximo). Si no hay hallazgos, retorna (None, "").
        """
        url = f"{self._url_base}/api/results/{job_id}"
        intentos = 0
        max_intentos = 18 # 18 * 5s = 90 segundos máximo de espera
        
        while intentos < max_intentos:
            try:
                with httpx.Client(auth=self._auth) as client:
                    response = client.get(url, timeout=10.0)
                    response.raise_for_status()
                    data = response.json()
                    
                    estado = data.get("estado")
                    
                    if estado == "procesando":
                        time.sleep(5)
                        intentos += 1
                        continue
                        
                    if estado == "finalizado":
                        # Extraemos siempre el ID, ya que sirve para descargar el certificado de 'limpio'
                        reporte_id = data.get("id")
                        if data.get("hallazgo"):
                            return reporte_id, data.get("hallazgos", "ALTO")
                        else:
                            return reporte_id, "NINGUNO"
                            
                    # Si el estado es "error" o viene en el diccionario {"error": "..."}
                    error_msg = data.get("error") if isinstance(data.get("error"), str) else "Error desconocido reportado por Tusdatos."
                    raise ErrorConsultaListas(f"La consulta falló internamente en el proveedor: {error_msg}")
                    
            except httpx.HTTPStatusError as e:
                raise ErrorConsultaListas(f"Error {e.response.status_code} consultando el estado del Job: {e.response.text}")
            except httpx.RequestError:
                # Tolerancia a pequeños cortes de red durante el polling
                time.sleep(5)
                intentos += 1
                
        raise ErrorConsultaListas("Tiempo de espera agotado (Timeout) esperando respuesta del proveedor.")

    def _obtener_reporte_json(self, reporte_id: str, riesgo_maximo: str) -> ResultadoConsultaListas:
        """
        Paso 3: Obtiene el JSON del reporte y extrae los hallazgos para armar el detalle descriptivo.
        """
        url = f"{self._url_base}/api/report_json/{reporte_id}"
        
        try:
            with httpx.Client(auth=self._auth) as client:
                response = client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                
                dict_hallazgos = data.get("dict_hallazgos", {})
                detalles_list = []
                
                # Iteramos solo por los riesgos que nos importan para resumirlos
                for categoria in ["altos", "medios", "bajos"]:
                    hallazgos_cat = dict_hallazgos.get(categoria, [])
                    for h in hallazgos_cat:
                        fuente = h.get("fuente", "Desconocida")
                        codigo = h.get("codigo", "sin_codigo")
                        descripcion = h.get("hallazgo", h.get("descripcion", ""))
                        
                        detalles_list.append(f"[{categoria.upper()}] Fuente: {fuente} (Código: {codigo}). {descripcion}")
                        
                texto_detalles = " | ".join(detalles_list) if detalles_list else "El proveedor reportó hallazgos pero no proveyó detalles."
                
                return ResultadoConsultaListas(
                    encontrado=True,
                    nivel_riesgo=riesgo_maximo.upper(),
                    detalles=texto_detalles,
                    fecha_consulta=datetime.utcnow().isoformat(),
                    reporte_id=reporte_id
                )
                
        except httpx.HTTPStatusError as e:
            raise ErrorConsultaListas(f"Error HTTP {e.response.status_code} extrayendo detalles del reporte: {e.response.text}")
        except httpx.RequestError as e:
            raise ErrorConsultaListas(f"Error de red descargando el reporte JSON final: {str(e)}")

    def descargar_pdf(self, reporte_id: str) -> bytes:
        """
        Descarga el PDF oficial de Tusdatos.
        Nota: Se asume endpoint universal /api/v2/report_pdf/. Si falla para NITs, 
        se debería adaptar a /api/report_nit_pdf/{id}.
        """
        url = f"{self._url_base}/api/v2/report_pdf/{reporte_id}"
        
        try:
            with httpx.Client(auth=self._auth) as client:
                response = client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError as e:
            raise ErrorConsultaListas(f"Error {e.response.status_code} descargando el certificado PDF: {e.response.text}")
        except httpx.RequestError as e:
            raise ErrorConsultaListas(f"Error de red intentando descargar el certificado PDF: {str(e)}")
