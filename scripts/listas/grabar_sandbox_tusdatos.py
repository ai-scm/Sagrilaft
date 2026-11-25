#!/usr/bin/env python3
"""Graba las respuestas del ambiente de pruebas de Tusdatos para usarlas como mocks.

Solo habla con el sandbox público (http://docs.tusdatos.co), con el usuario de pruebas
que Tusdatos publica en su documentación. Las respuestas son estáticas y ficticias:
no consume créditos ni envía datos nuestros. Nunca apunta a producción.

Uso:  python scripts/listas/grabar_sandbox_tusdatos.py [--destino DIR]
"""
import argparse
import base64
import json
from pathlib import Path

import httpx

SANDBOX = "http://docs.tusdatos.co"
USUARIO_PRUEBAS = ("pruebas", "password")  # Publicado por Tusdatos para su sandbox.
DESTINO = Path(__file__).resolve().parents[2] / "tests/fixtures/tusdatos_sandbox"

# Casos documentados por Tusdatos (identificadores tomados de su documentación).
CASOS = [
    ("launch_cc_con_hallazgo", "POST", "/api/launch", {"doc": 111, "typedoc": "CC", "fechaE": "01/12/2014"}),
    ("launch_cc_sin_hallazgo", "POST", "/api/launch", {"doc": 112, "typedoc": "CC", "fechaE": "01/12/2014"}),
    ("launch_cc_en_cache", "POST", "/api/launch", {"doc": 126, "typedoc": "CC"}),
    ("launch_cc_forzada", "POST", "/api/launch", {"doc": 127, "typedoc": "CC", "fechaE": "05/01/2015", "force": True}),
    ("launch_cc_titular_no_autoriza", "POST", "/api/launch", {"doc": 128, "typedoc": "CC", "fechaE": "08/06/2007"}),
    ("launch_ce", "POST", "/api/launch", {"doc": 960696, "typedoc": "CE", "fechaE": "01/11/2001"}),
    ("launch_pp", "POST", "/api/launch", {"doc": "381310014", "name": "JUAN PEREZ PEREZ", "typedoc": "PP"}),
    ("launch_nit", "POST", "/api/launch", {"doc": 900000152, "typedoc": "NIT"}),
    ("launch_invalido", "POST", "/api/launch", {"typedoc": "C"}),
    ("results_procesando", "GET", "/api/results/6769d210-3476-4c82-a044-045e9d5bc157", None),
    ("results_con_hallazgo", "GET", "/api/results/6460fc34-4154-43db-9438-8c5a059304c0", None),
    ("results_sin_hallazgo", "GET", "/api/results/5c6c80c0-4dd3-41c9-9648-46871a7176ad", None),
    ("results_con_error", "GET", "/api/results/485e9823-df75-4b1e-9f64-58916a82dfd7", None),
    ("results_inexistente", "GET", "/api/results/00000000-0000-0000-0000-000000000000", None),
    ("results_nit", "GET", "/api/results/e7451a5e-97ca-498e-a7f0-a352658cbc26", None),
    ("report_cc_con_hallazgo", "GET", "/api/report_json/651c2ede72476080772781f5", None),
    ("report_cc_sin_hallazgo", "GET", "/api/report_json/8188f7e8aa70102bf2053f32", None),
    ("report_cc_con_error", "GET", "/api/report_json/d9530d51473cf57e73945088", None),
    ("report_nit", "GET", "/api/report_json/5d9e05963817a56d989523c0", None),
    ("pdf_persona", "GET", "/api/v2/report_pdf/5d9e00483800a5071688a101", None),
    ("pdf_nit", "GET", "/api/v2/report_nit_pdf/5d9e05963817a56d989523c0", None),
    ("retry_cc", "GET", "/api/retry/7d1f10483800b5071688e101?typedoc=CC", None),
    ("estado_fuentes", "GET", "/api/v1/sources/status?country=CO", None),
    ("plan", "GET", "/api/plans", None),
]


def grabar(cliente, metodo, ruta, cuerpo):
    respuesta = cliente.request(metodo, ruta, json=cuerpo)
    tipo = respuesta.headers.get("content-type", "")
    grabada = {"estado": respuesta.status_code, "tipo": tipo,
               "encabezados": {k: v for k, v in respuesta.headers.items() if k.lower() in {"retry-after"}}}
    if "json" in tipo:
        grabada["json"] = respuesta.json()
    else:
        grabada["base64"] = base64.b64encode(respuesta.content).decode()
    return grabada


def principal():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--destino", type=Path, default=DESTINO)
    destino = argumentos.parse_args().destino
    destino.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=SANDBOX, auth=USUARIO_PRUEBAS, timeout=30) as cliente:
        sin_credenciales = httpx.get(SANDBOX + CASOS[10][2], timeout=30)
        casos = {"sin_credenciales": {"peticion": {"metodo": "GET", "ruta": CASOS[10][2], "cuerpo": None},
                                      "respuesta": {"estado": sin_credenciales.status_code, "tipo": sin_credenciales.headers.get("content-type", ""),
                                                    "encabezados": {}, "json": sin_credenciales.json() if "json" in sin_credenciales.headers.get("content-type", "") else None}}}
        for nombre, metodo, ruta, cuerpo in CASOS:
            casos[nombre] = {"peticion": {"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo},
                             "respuesta": grabar(cliente, metodo, ruta, cuerpo)}
            print(f"{nombre:32} {casos[nombre]['respuesta']['estado']}")
    (destino / "casos.json").write_text(json.dumps(casos, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    principal()
