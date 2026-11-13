"""Traducción de Advanced ya importado. Los códigos OFAC no salen de este adaptador."""

from dataclasses import dataclass

from domain.listas.datos_busqueda import (
    FechaDato, HechoFecha, HechoTexto, HechoUbicacion, IdentificadorFuente,
    NombreFuente, ParteNombre, PartesFecha, RegistroBusqueda, UbicacionContexto,
)
from infrastructure.listas.adaptador_ofac import recorrer
from infrastructure.listas.catalogos_ofac import CALIDADES_OFAC_ADVANCED

VERSION_ADAPTADOR = "ofac-advanced-busqueda-v2"  # v2: "Cedula No." se interpreta como CC solo si el país emisor es Colombia

# No se equipara cualquier «cédula» extranjera con una CC colombiana: "Cedula No." (1570)
# es una etiqueta genérica que OFAC reutiliza para el documento nacional de varios países
# (Venezuela la usa más que Colombia). Se interpreta como CC solo cuando el propio registro
# declara el país emisor como Colombia (ver DOCUMENTO_NACIONAL_CONDICIONADO más abajo); en
# cualquier otro caso, o sin país identificado, se conserva sin comparar.
DOCUMENTOS = {"1571": "PASAPORTE", "1575": "NIT", "1581": "REGISTRO_EMPRESARIAL"}
DOCUMENTO_NACIONAL_CONDICIONADO = {"1570": "CC"}  # código OFAC -> tipo, solo si pais_emisor == "CO"
CAMPOS = {"8": "fecha_nacimiento", "9": "lugar_nacimiento", "10": "nacionalidad",
          "11": "ciudadania", "13": "bic", "14": "sitio_web"}


def hijos(nodo, etiqueta):
    return [h for h in nodo.get("hijos", ()) if h["etiqueta"] == etiqueta]


def texto(nodo, etiqueta):
    return next((h.get("texto", "") for h in recorrer(nodo, etiqueta)), "")


def verdadero(valor):
    return valor in ("true", "1")


def _original_legible(periodo):
    """Representación humana del nodo DatePeriod para trazabilidad y presentación."""
    calendario_id = periodo.get("atributos", {}).get("CalendarTypeID")
    if calendario_id != "1":
        return f"Calendario no interpretado (ID: {calendario_id})"
    puntos = []
    for borde in hijos(periodo, "Start") + hijos(periodo, "End"):
        for punto in borde.get("hijos", ()):
            if punto["etiqueta"] not in {"From", "To"}:
                continue
            anio = texto(punto, "Year")
            if not anio:
                continue
            partes = [anio.zfill(4)]
            mes = texto(punto, "Month")
            if mes:
                partes.append(mes.zfill(2))
                dia = texto(punto, "Day")
                if dia:
                    partes.append(dia.zfill(2))
            puntos.append("-".join(partes))
    aproximada = any(
        verdadero(b.get("atributos", {}).get("Approximate"))
        for b in hijos(periodo, "Start") + hijos(periodo, "End"))
    prefijo = "~" if aproximada else ""
    if not puntos:
        return "Fecha sin componentes extraíbles"
    unicos = list(dict.fromkeys(puntos))
    if len(unicos) == 1:
        return f"{prefijo}{unicos[0]}"
    return f"{prefijo}{unicos[0]} a {unicos[-1]}"


def interpretar_fecha(periodo):
    original = _original_legible(periodo)
    calendario = "GREGORIANO" if periodo["atributos"].get("CalendarTypeID") == "1" else "NO_INTERPRETADO"
    sin_interpretar = FechaDato(original=original, calendario=calendario, precision="NO_INTERPRETADA")
    if calendario != "GREGORIANO":
        return sin_interpretar
    limites = []
    aproximada = False
    for borde in hijos(periodo, "Start") + hijos(periodo, "End"):
        atributos = dict(borde["atributos"])
        for componente in ("YearFixed", "MonthFixed", "DayFixed"):
            atributos[componente] = "true" if all(verdadero(n.get(componente)) for n in (periodo["atributos"], borde["atributos"])) else "false"
        aproximada |= verdadero(atributos.get("Approximate"))
        if not verdadero(atributos.get("YearFixed")):
            return sin_interpretar
        for punto in borde.get("hijos", ()):
            if punto["etiqueta"] not in {"From", "To"}:
                continue
            try:
                anio = int(texto(punto, "Year"))
                mes = int(texto(punto, "Month")) if verdadero(atributos.get("MonthFixed")) else None
                dia = int(texto(punto, "Day")) if mes and verdadero(atributos.get("DayFixed")) else None
                limites.append(PartesFecha(anio=anio, mes=mes, dia=dia))
            except ValueError:
                return sin_interpretar
    # Un límite aislado no se convierte en nacimiento exacto.
    if len(limites) < 2:
        return sin_interpretar
    if all(p == limites[0] for p in limites):
        valor = limites[0]
        return FechaDato(original=original, calendario=calendario, valor=valor,
            precision="DIA" if valor.dia else "MES" if valor.mes else "ANIO", aproximada=aproximada)
    if len(limites) != 2:
        return sin_interpretar
    return FechaDato(original=original, calendario=calendario, precision="RANGO",
        desde=limites[0], hasta=limites[1], aproximada=aproximada)


@dataclass
class _LecturaOfac:
    contenido: dict
    referencia: object
    catalogo: object

    def referencia_de(self, camino, identidad=None):
        return self.referencia.model_copy(update={"campo_original": camino, "identidad_origen": identidad})

    def pais(self, identificador):
        nodo = self.catalogos.get(("Country", identificador), {})
        return nodo.get("atributos", {}).get("ISO2")

    def pais_declarado(self, valor):
        explicito = self.catalogo.pais(valor)
        if explicito:
            return explicito
        equivalencias = {n["atributos"].get("ISO2") for (tipo, _), n in self.catalogos.items()
                        if tipo == "Country" and n.get("texto", "").strip().casefold() == valor.strip().casefold()}
        equivalencias.discard(None)
        return next(iter(equivalencias)) if len(equivalencias) == 1 else None

    def ubicaciones(self, lugar_id, rol, referencia, calidad):
        lugar = self.lugares.get(lugar_id)
        if lugar is None:
            self.pendientes.append(referencia.campo_original)
            return []
        textos = [n["texto"] for n in recorrer(lugar, "Value") if n.get("texto", "").strip()]
        paises = [self.pais(n["atributos"].get("CountryID")) for n in recorrer(lugar, "LocationCountry")]
        valores = [p for p in paises if p] or [None]
        if not textos and not any(paises):
            self.pendientes.append(referencia.campo_original)
        return [HechoUbicacion(campo="ubicacion", calidad=calidad, referencia=referencia,
            valor=UbicacionContexto(rol=rol, texto=", ".join(textos) or None, pais=p))
            for p in valores if p or textos]

    def ejecutar(self):
        self.catalogos = {(n["etiqueta"], n["atributos"]["ID"]): n for n in self.contenido["catalogos"]}
        self.lugares = {n["atributos"]["ID"]: n for n in self.contenido["ubicaciones"]}
        self.pendientes = []
        nombres, identificadores, hechos = [], [], []
        identidades = {}
        for identidad in recorrer(self.contenido["sujeto"], "Identity"):
            identidad_id = identidad["atributos"]["ID"]
            falsa = verdadero(identidad["atributos"].get("False"))
            identidades[identidad_id] = falsa
            grupos = {n["atributos"]["ID"]: n["atributos"].get("NamePartTypeID", "DESCONOCIDO")
                      for n in recorrer(identidad, "NamePartGroup")}
            for alias in hijos(identidad, "Alias"):
                for documento in hijos(alias, "DocumentedName"):
                    alfabetos = {}
                    for parte in recorrer(documento, "NamePartValue"):
                        alfabetos.setdefault(parte["atributos"].get("ScriptID"), []).append(parte)
                    for alfabeto, partes in alfabetos.items():
                        referencia = self.referencia_de(f"Identity/{identidad_id}/DocumentedName/{documento['atributos']['ID']}/{alfabeto}", identidad_id)
                        tipo = "PRINCIPAL" if verdadero(alias["atributos"].get("Primary")) else "ANTERIOR" if alias["atributos"].get("AliasTypeID") == "1401" else "ALIAS"
                        nombres.append(NombreFuente(valor=" ".join(p["texto"] for p in partes), tipo=tipo,
                            alias_debil=verdadero(alias["atributos"].get("LowQuality")), alfabeto=alfabeto,
                            partes=[ParteNombre(tipo=grupos.get(p["atributos"].get("NamePartGroupID"), "DESCONOCIDO"), valor=p["texto"]) for p in partes],
                            calidad="FALSO" if falsa else "DESCONOCIDO", referencia=referencia))
        for documento in self.contenido["documentos"]:
            atributos = documento["atributos"]
            codigo = atributos["IDRegDocTypeID"]
            pais_emisor_documento = self.pais(atributos.get("IssuedBy-CountryID"))
            if codigo in DOCUMENTO_NACIONAL_CONDICIONADO and pais_emisor_documento == "CO":
                tipo = DOCUMENTO_NACIONAL_CONDICIONADO[codigo]
            else:
                tipo = DOCUMENTOS.get(codigo, "OFAC_DOCUMENTO:" + codigo)
            definicion = self.catalogo.identificador(tipo)
            esquema = definicion.esquema if definicion else None
            referencia = self.referencia_de("IDRegDocument/" + atributos["ID"], atributos["IdentityID"])
            # ValidityID no es ReliabilityID. No se convierte un documento «válido» en confirmado.
            calidad = "FALSO" if (identidades.get(atributos["IdentityID"]) or atributos.get("ValidityID") == "2") else "DESCONOCIDO"
            validez = self.catalogos.get(("Validity", atributos.get("ValidityID")), {}).get("texto")
            if validez:
                hechos.append(HechoTexto(campo="validez_documento", valor=validez, referencia=referencia))
            numero = texto(documento, "IDRegistrationNo")
            if numero.strip():
                identificadores.append(IdentificadorFuente(tipo=tipo, esquema=esquema,
                    valor=numero, pais_emisor=pais_emisor_documento,
                    calidad=calidad, referencia=referencia))
            else:
                self.pendientes.append(referencia.campo_original)
            for ordinal, fecha in enumerate(hijos(documento, "DocumentDate")):
                codigo_fecha = fecha["atributos"]["IDRegDocDateTypeID"]
                campo_fecha = {"1480": "fecha_expedicion", "1481": "fecha_vencimiento"}.get(codigo_fecha, "OFAC_FECHA:" + codigo_fecha)
                for periodo in hijos(fecha, "DatePeriod"):
                    hechos.append(HechoFecha(campo=campo_fecha, valor=interpretar_fecha(periodo), calidad=calidad,
                        referencia=self.referencia_de(f"IDRegDocument/{atributos['ID']}/DocumentDate/{ordinal}", atributos["IdentityID"])))
            if atributos.get("IssuedIn-LocationID"):
                hechos.extend(self.ubicaciones(atributos["IssuedIn-LocationID"], "EMISION", referencia, calidad))
            if esquema is None:
                self.pendientes.append(referencia.campo_original)
        for caracteristica in recorrer(self.contenido["sujeto"], "Feature"):
            codigo = caracteristica["atributos"]["FeatureTypeID"]
            campo = CAMPOS.get(codigo, "OFAC_CARACTERISTICA:" + codigo)
            referencias = [n["atributos"]["IdentityID"] for n in hijos(caracteristica, "IdentityReference")]
            for variante in hijos(caracteristica, "FeatureVersion"):
                for identidad_id in referencias or [None]:
                    referencia = self.referencia_de("FeatureVersion/" + variante["atributos"]["ID"], identidad_id)
                    calidad = CALIDADES_OFAC_ADVANCED.resolver(variante["atributos"].get("ReliabilityID"))
                    if identidad_id and identidades.get(identidad_id):
                        calidad = "FALSO"
                    if codigo not in CAMPOS or identidad_id is None:
                        self.pendientes.append(referencia.campo_original)
                    for periodo in hijos(variante, "DatePeriod"):
                        fecha = interpretar_fecha(periodo)
                        hechos.append(HechoFecha(campo=campo, valor=fecha, referencia=referencia, calidad=calidad))
                        if fecha.precision == "NO_INTERPRETADA":
                            self.pendientes.append(referencia.campo_original)
                    for detalle in hijos(variante, "VersionDetail"):
                        valor = detalle.get("texto", "")
                        identificador_detalle = detalle["atributos"].get("DetailReferenceID")
                        if not valor.strip() and identificador_detalle:
                            valor = self.catalogos.get(("DetailReference", identificador_detalle), {}).get("texto", "")
                        if valor.strip():
                            if codigo in {"10", "11"}:
                                pais = self.pais_declarado(valor)
                                if pais:
                                    valor = pais
                                else:
                                    self.pendientes.append(referencia.campo_original)
                            hechos.append(HechoTexto(campo=campo, valor=valor, referencia=referencia, calidad=calidad))
                        else:
                            self.pendientes.append(referencia.campo_original)
                    for lugar in hijos(variante, "VersionLocation"):
                        rol = "NACIMIENTO" if codigo == "9" else "OTRO"
                        hechos.extend(self.ubicaciones(lugar["atributos"]["LocationID"], rol, referencia, calidad))
        for ordinal, comentario in enumerate(recorrer(self.contenido["sujeto"], "Comment")):
            if comentario.get("texto", "").strip():
                hechos.append(HechoTexto(campo="observacion", valor=comentario["texto"],
                    referencia=self.referencia_de(f"Comment/{ordinal}")))
        for seccion in ("sanciones", "enlaces"):
            if self.contenido.get(seccion):
                self.pendientes.append(seccion)
        return RegistroBusqueda(tipo_sujeto=self.contenido["clase"], referencia=self.referencia,
            nombres=nombres, identificadores=identificadores, hechos=hechos), tuple(sorted(set(self.pendientes)))


def interpretar(contenido, referencia, catalogo):
    return _LecturaOfac(contenido, referencia, catalogo).ejecutar()
