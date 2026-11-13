"""Contrastes de fechas y contexto sin convertir ausencias en contradicciones."""
from calendar import monthrange
from datetime import date

from .contratos_busqueda import MotivoClasificacion


def motivo(campo, resultado, metodo, explicacion, consultado=None, publicado=None, dato=None):
    return MotivoClasificacion(campo=campo, resultado=resultado, metodo=metodo,
        explicacion=explicacion, valor_consultado=consultado, valor_fuente=publicado,
        calidad_fuente=dato.calidad if dato else "DESCONOCIDO",
        referencia=dato.referencia if dato else None)


def limite_fecha(partes, superior=False):
    mes = partes.mes or (12 if superior else 1)
    dia = partes.dia or (monthrange(partes.anio, mes)[1] if superior else 1)
    return date(partes.anio, mes, dia)


def contraste_fecha(consultada, hecho):
    fecha = hecho.valor
    if fecha.precision == "NO_INTERPRETADA" or hecho.calidad == "FALSO":
        return "NO_APLICADO", False
    if fecha.precision == "RANGO":
        compatible = limite_fecha(fecha.desde) <= consultada <= limite_fecha(fecha.hasta, True)
    else:
        compatible = limite_fecha(fecha.valor) <= consultada <= limite_fecha(fecha.valor, True)
    fuerte = fecha.precision == "DIA" and not fecha.aproximada and hecho.calidad == "CONFIRMADO"
    return ("COINCIDE" if fuerte else "COMPATIBLE") if compatible else "DIFERENTE", fuerte


def misma_identidad(uno, otro, registro):
    a, b = uno.referencia.identidad_origen, otro.referencia.identidad_origen
    identidades = {d.referencia.identidad_origen for d in (*registro.nombres, *registro.identificadores, *registro.hechos)
                   if d.referencia.identidad_origen is not None}
    return a == b and (a is not None or not identidades)
