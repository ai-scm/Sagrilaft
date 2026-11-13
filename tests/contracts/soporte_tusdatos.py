"""Simulador de Tusdatos para pruebas: responde con lo grabado del sandbox y con casos escritos a mano."""
import base64
import json
from pathlib import Path

import httpx

CASOS = Path(__file__).resolve().parents[1] / "fixtures/tusdatos_sandbox/casos.json"
# PDF mínimo válido: el sandbox no entrega PDF reales (responde un texto JSON).
PDF_MINIMO = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
              b"trailer<</Root 1 0 R>>\n%%EOF\n")


def _respuesta(grabada):
    encabezados = dict(grabada.get("encabezados") or {})
    if "json" in grabada:
        return httpx.Response(grabada["estado"], json=grabada["json"], headers=encabezados)
    return httpx.Response(grabada["estado"], content=base64.b64decode(grabada.get("base64", "")),
                          headers={"content-type": grabada.get("tipo", ""), **encabezados})


class SimuladorTusdatos:
    """`extras` reemplaza rutas: {(metodo, ruta): httpx.Response | Exception | callable | [secuencia]}."""

    def __init__(self, extras=None):
        self.casos = json.loads(CASOS.read_text())
        self.lanzamientos, self.lecturas = {}, {}
        for nombre, caso in self.casos.items():
            peticion = caso["peticion"]
            if peticion["metodo"] == "POST" and peticion["ruta"] == "/api/launch":
                cuerpo = peticion["cuerpo"] or {}
                self.lanzamientos[(str(cuerpo.get("doc")), cuerpo.get("typedoc"))] = caso["respuesta"]
            elif nombre != "sin_credenciales":
                self.lecturas[peticion["ruta"].split("?")[0]] = caso["respuesta"]
        self.extras = {clave: list(valor) if isinstance(valor, list) else valor for clave, valor in (extras or {}).items()}
        self.peticiones: list[httpx.Request] = []
        self.transporte = httpx.MockTransport(self._manejar)

    def cuerpos(self):
        return [json.loads(p.content) for p in self.peticiones if p.content]

    def _manejar(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        clave = (peticion.method, peticion.url.path)
        if clave in self.extras:
            respuesta = self.extras[clave]
            if isinstance(respuesta, list):
                respuesta = respuesta.pop(0) if len(respuesta) > 1 else respuesta[0]
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta(peticion) if callable(respuesta) else respuesta
        if "authorization" not in peticion.headers:
            return _respuesta(self.casos["sin_credenciales"]["respuesta"])
        if clave == ("POST", "/api/launch"):
            cuerpo = json.loads(peticion.content)
            grabada = self.lanzamientos.get((str(cuerpo.get("doc")), cuerpo.get("typedoc")))
            if grabada is None:
                return _respuesta(self.casos["launch_invalido"]["respuesta"])
            return _respuesta(grabada)
        grabada = self.lecturas.get(peticion.url.path)
        return _respuesta(grabada) if grabada else httpx.Response(404, json={"detail": "Not Found"})
