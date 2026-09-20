"""Reglas RBAC compartidas del portal interno."""

from api.middleware.autenticacion import UsuarioPortalInterno
from domain.excepciones import SinPermisoError

ROLES_A_CONTRAPARTES = {
    "acceso_clientes": "cliente",
    "acceso_proveedores": "proveedor",
}


def contrapartes_permitidas(usuario: UsuarioPortalInterno) -> list[str]:
    """Deriva las carpetas visibles según los roles Keycloak del operador."""

    permitidas = [
        tipo
        for rol, tipo in ROLES_A_CONTRAPARTES.items()
        if usuario.tiene_rol(rol)
    ]

    if not permitidas:
        raise SinPermisoError("sin_roles")

    return permitidas
