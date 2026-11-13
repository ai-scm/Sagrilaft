"""Ruta retirada: las consultas requieren expediente y permisos del portal."""
from fastapi import APIRouter, Depends, HTTPException
from api.middleware.autenticacion import portal_interno

enrutador = APIRouter(prefix="/api/listas-cautela", tags=["listas de cautela"])

@enrutador.post("/buscar", deprecated=True, dependencies=[Depends(portal_interno)])
def buscar_en_listas():
    raise HTTPException(410, "La búsqueda independiente está deshabilitada; use consultas por expediente")
