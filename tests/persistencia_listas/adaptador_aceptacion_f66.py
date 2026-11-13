"""Fuente de aceptación ficticia: hechos explícitos en observación JSON de XML sintético.

Se registra solo mediante monkeypatch. Nunca forma parte del catálogo de producción.
"""
import json
from lxml import etree
from domain.listas.datos_busqueda import RegistroBusqueda

VERSION_ADAPTADOR = "aceptacion-sintetica-f66-v1"


def xml_de_registros(registros):
    raiz = etree.Element("{urn:sagrilaft:pruebas:listas:v1}lista",nsmap={None:"urn:sagrilaft:pruebas:listas:v1"},sintetica="true")
    for indice,registro in enumerate(registros):
        elemento = etree.SubElement(raiz,"registro",uid=f"r_{indice}",clase=registro.tipo_sujeto)
        etree.SubElement(elemento,"nombre").text = registro.nombres[0].valor
        etree.SubElement(elemento,"observacion").text = registro.model_dump_json()
    return etree.tostring(raiz,encoding="utf-8")


def interpretar(contenido,referencia,catalogo):
    datos = json.loads(next(c["texto"] for c in contenido["campos"] if c["tipo"] == "observacion"))
    def fijar(objeto):
        if isinstance(objeto,list):
            return [fijar(v) for v in objeto]
        if isinstance(objeto,dict):
            salida = {k:fijar(v) for k,v in objeto.items()}
            if {"campo_original","fuente_codigo","version_id","registro_id"} <= salida.keys():
                salida.update(fuente_codigo=referencia.fuente_codigo,version_id=str(referencia.version_id),registro_id=str(referencia.registro_id))
            return salida
        return objeto
    return RegistroBusqueda.model_validate(fijar(datos)), ()
