"""Pantalla, PDF y compatibilidad histórica con registros Advanced ficticios."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from sqlalchemy import select, text

from infrastructure.listas.consultor_archivos import ConsultorArchivos
from infrastructure.persistencia.modelos_listas import BorradorConsulta
from .test_integracion_f64 import archivos, crear, detalle
from .test_administracion_f55 import administracion
from .test_recepcion_f52 import carga
from .test_flujo_http import portal


@pytest.mark.parametrize("nacimiento,nivel", [("1980-03-15","ALTA"),(None,"MEDIA"),("1985-03-15","BAJA")])
def test_f65_pdf_legible_con_motivos_trazabilidad_y_sin_puntajes(archivos, tmp_path, nacimiento, nivel):
    a = archivos
    identificador = crear(a,nacimiento=nacimiento).json()["consulta_id"]
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a,identificador)
    candidato = consulta["candidatos"][0]
    assert candidato["nivel"] == nivel
    assert candidato["nombres"] and candidato["identificadores"] and candidato["hechos"] and candidato["relaciones"]
    assert consulta["trazabilidad"]["fuentes"][0]["generacion_id"] == str(a.generacion)
    evidencia = consulta["evidencias"][0]
    assert evidencia["generador_version"] == "informe-listas-f6-v2"
    ruta = f"/api/consultas-listas/{identificador}/evidencias/{evidencia['id']}"
    pdf = a.cliente.get(ruta)
    assert pdf.status_code == 200
    archivo = tmp_path / "informe.pdf"
    archivo.write_bytes(pdf.content)
    contenido = subprocess.check_output(["pdftotext", "-layout", str(archivo), "-"],text=True)
    for esperado in (nivel,candidato["explicacion"].split('.')[0],str(a.version),str(a.generacion),
                     "Dato consultado","Dato de la fuente","Calidad publicada","Relación publicada",
                     "requieren revisión humana", "Hash del resultado"):
        assert esperado in " ".join(contenido.split()), (esperado,contenido)
    assert '"puntaje"' not in contenido and '"parametros"' not in contenido and "%" not in contenido
    a.cliente.headers["Authorization"] = "Bearer " + a.token(["acceso_proveedores","listas_revisor"])
    assert a.cliente.get(ruta).status_code == 404
    a.cliente.headers["Authorization"] = "Bearer " + a.token()
    assert a.cliente.get(ruta).content == pdf.content
    directorio = Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"])
    (directorio / f"informe-f65-{nivel}.pdf").write_bytes(pdf.content)
    (directorio / f"informe-f65-{nivel}.txt").write_text(contenido)


def test_f65_borrador_anterior_conserva_generador_y_bytes(archivos,monkeypatch):
    a = archivos
    identificador = crear(a).json()["consulta_id"]
    consultar = ConsultorArchivos.consultar
    def formato_anterior(self,solicitud):
        resultado = consultar(self,solicitud)
        return resultado.model_copy(update={"generador_informe_version":"informe-listas-v1"})
    monkeypatch.setattr("infrastructure.listas.consultor_archivos.ConsultorArchivos.consultar", formato_anterior)
    original = a.trabajador.repositorio.cerrar
    def interrumpir(*_):
        raise RuntimeError("Interrupción antes del cierre")
    monkeypatch.setattr(a.trabajador.repositorio,"cerrar",interrumpir)
    with pytest.raises(RuntimeError,match="Interrupción"):
        a.trabajador.ejecutar_uno()
    with a.sesiones.begin() as sesion:
        borrador = sesion.scalar(select(BorradorConsulta))
        pdf_anterior = a.custodia.leer(borrador.informe_clave,borrador.informe_huella,borrador.informe_tamano)
        sesion.execute(text("UPDATE trabajo_consulta SET concesion_hasta=now()-interval '1 second' WHERE consulta_id=:id"),{"id":identificador})
    monkeypatch.setattr(a.trabajador.repositorio,"cerrar",original)
    monkeypatch.setattr(a.trabajador.repositorio,"generar_informe",lambda *_: pytest.fail("No se regenera el PDF anterior"))
    assert a.trabajador.ejecutar_uno()
    consulta = detalle(a,identificador)
    evidencia = consulta["evidencias"][0]
    assert evidencia["generador_version"] == "informe-listas-v1"
    ruta = f"/api/consultas-listas/{identificador}/evidencias/{evidencia['id']}"
    assert a.cliente.get(ruta).content == pdf_anterior


def test_f65_pantalla_tres_niveles_dos_circuitos_y_evidencias(archivos,tmp_path):
    from .test_flujo_http import test_navegador_con_api_postgres_y_trabajador_reales as recorrido
    recorrido(archivos,tmp_path,"ninguno",verificar_presentacion=True)
    directorio = Path(os.environ["LISTAS_EVIDENCIAS_DIRECTORIO"])
    shutil.copyfile(directorio / "portal-ninguno.png",directorio / "portal-f65.png")
