"""Traduce registros sintéticos importados al modelo común de búsqueda."""
from domain.listas.datos_busqueda import (
    HechoTexto, HechoUbicacion, IdentificadorFuente, NombreFuente, RegistroBusqueda, UbicacionContexto,
)

VERSION_ADAPTADOR = "sintetico-busqueda-v1"


def interpretar(contenido, referencia, catalogo):
    nombres, identificadores, hechos, pendientes = [], [], [], []
    for ordinal, campo in enumerate(contenido["campos"]):
        origen = referencia.model_copy(update={"campo_original": f"campos/{ordinal}"})
        tipo, valor, atributos = campo["tipo"], campo["texto"], campo["atributos"]
        if tipo in {"nombre", "alias"}:
            nombres.append(NombreFuente(valor=valor, tipo="PRINCIPAL" if tipo == "nombre" else "ALIAS", referencia=origen))
        elif tipo == "identificador":
            definicion = catalogo.identificador(atributos["tipo"])
            identificadores.append(IdentificadorFuente(
                tipo=definicion.tipo if definicion else atributos["tipo"],
                esquema=definicion.esquema if definicion else None,
                valor=valor, pais_emisor=atributos.get("pais"), referencia=origen))
            if not definicion:
                pendientes.append(origen.campo_original)
        elif tipo == "direccion":
            hechos.append(HechoUbicacion(campo="ubicacion", valor=UbicacionContexto(rol="DOMICILIO", texto=valor), referencia=origen))
        elif tipo == "observacion":
            hechos.append(HechoTexto(campo="observacion", valor=valor, referencia=origen))
        elif tipo != "relacion":
            pendientes.append(origen.campo_original)
    return RegistroBusqueda(tipo_sujeto=contenido["clase"], referencia=referencia,
        nombres=nombres, identificadores=identificadores, hechos=hechos), tuple(pendientes)
