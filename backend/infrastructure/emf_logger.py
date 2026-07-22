"""
Helper para emitir métricas en formato AWS EMF (Embedded Metric Format).
Permite graficar métricas de negocio directamente desde los logs sin usar la API de CloudWatch.
"""
import json
import time
from typing import Dict, Optional

def emitir_metrica_emf(
    namespace: str,
    dimensiones: Dict[str, str],
    metricas: Dict[str, float]
) -> None:
    """
    Emite un log en formato AWS EMF.
    
    Args:
        namespace: Espacio de nombres de la métrica (ej. 'Sagrilaft/Negocio')
        dimensiones: Diccionario de dimensiones (ej. {'Servicio': 'Bedrock'})
        metricas: Diccionario de métricas y sus valores numéricos
    """
    metrics_array = [{"Name": k, "Unit": "Count" if "Latency" not in k else "Milliseconds"} for k in metricas.keys()]
    dimension_keys = list(dimensiones.keys())
    
    emf_payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [dimension_keys],
                    "Metrics": metrics_array
                }
            ]
        }
    }
    
    emf_payload.update(dimensiones)
    emf_payload.update(metricas)
    
    # CloudWatch Logs agent busca JSONs válidos empezando con {"_aws"
    print(json.dumps(emf_payload))
