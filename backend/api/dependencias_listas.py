"""Composición del módulo: identidad validada, acceso por expediente y custodia (local o S3)."""
from fastapi import Depends, Request, HTTPException
from api.middleware.autenticacion import portal_interno, UsuarioPortalInterno
from api.rbac import contrapartes_permitidas
from infrastructure.persistencia.database import SessionLocal
from infrastructure.listas.custodia import CustodiaLocalListas, custodia_desde_entorno
from services.listas.politica_v2 import ActorListas, PoliticaListasV2
from services.listas.servicio_comun import ServicioComunListas


def sesiones_listas():
    return SessionLocal


def custodia_listas():
    try:
        custodia = custodia_desde_entorno()
    except ValueError as error:
        raise HTTPException(503, "Custodia de listas mal configurada") from error
    if custodia is None:
        raise HTTPException(503, "Custodia de listas no configurada")
    return custodia


def custodia_administrativa(custodia=Depends(custodia_listas)):
    """Recepción, validación e importación trabajan sobre disco: solo con custodia local."""
    if not isinstance(custodia, CustodiaLocalListas):
        raise HTTPException(409, "La administración de listas requiere custodia local")
    return custodia


def servicio_listas(request: Request, usuario: UsuarioPortalInterno = Depends(portal_interno),
                    sesiones=Depends(sesiones_listas), custodia=Depends(custodia_listas)):
    configuracion = request.app.state.config
    actor = ActorListas.desde_identidad_validada(configuracion.keycloak.issuer, usuario.sub, tuple(usuario.roles))
    return ServicioComunListas(sesiones, PoliticaListasV2(configuracion.listas_cautela, configuracion.entorno),
                               custodia, actor, contrapartes_permitidas(usuario), entorno=configuracion.entorno)
