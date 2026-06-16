"""
Comparación estructurada entre versiones del formulario.

Compara snapshots guardados junto a cada PDF versionado. No interpreta el PDF:
usa los datos de negocio que originaron el documento, por eso es más confiable
para auditoría cuando el flujo fue digital.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from domain.catalogo_correcciones import (
    CAMPOS_IDENTIFICABLES_PARA_CORRECION,
    ETIQUETA_DE_CAMPO_EN_CORRECION,
)
from domain.contratos import DocumentoDatos
from services.formulario.formato_moneda import formatear_monto_monetario


_CAMPOS_EXCLUIDOS = frozenset({
    "id",
    "codigo_peticion",
    "numero_correccion",
    "dia_firma",
    "mes_firma",
    "year_firma",
    "ciudad_firma",
})

_CAMPOS_MONETARIOS = frozenset({
    "ingresos_mensuales",
    "otros_ingresos",
    "egresos_mensuales",
    "total_activos",
    "total_pasivos",
    "patrimonio",
})

_MOTIVO_SIN_VERSION_ANTERIOR = "No existe una versión anterior inmediata para comparar."
_MOTIVO_SNAPSHOT_AMBAS = "La comparación estructurada no está disponible porque faltan los snapshots de ambas versiones."
_MOTIVO_SNAPSHOT_ANTERIOR = "La comparación estructurada no está disponible porque falta el snapshot de la versión anterior."
_MOTIVO_SNAPSHOT_CORREGIDO = "La comparación estructurada no está disponible porque falta el snapshot de la versión corregida."

@dataclass(frozen=True)
class CambioCampo:
    campo: str
    etiqueta: str
    valor_anterior: str
    valor_corregido: str


@dataclass(frozen=True)
class ComparacionVersiones:
    disponible: bool
    motivo: Optional[str]
    version_anterior: int
    version_corregida: int
    moneda_anterior: Optional[str]
    moneda_corregida: Optional[str]
    documento_anterior_id: Optional[str]
    documento_corregido_id: str
    cambios: List[CambioCampo]


def comparacion_versiones_a_dict(comparacion: ComparacionVersiones) -> Dict[str, Any]:
    """Convierte la comparación de dominio al payload que expone la API."""
    return {
        "disponible": comparacion.disponible,
        "motivo": comparacion.motivo,
        "version_anterior": comparacion.version_anterior,
        "version_corregida": comparacion.version_corregida,
        "moneda_anterior": comparacion.moneda_anterior,
        "moneda_corregida": comparacion.moneda_corregida,
        "documento_anterior_id": comparacion.documento_anterior_id,
        "documento_corregido_id": comparacion.documento_corregido_id,
        "total_cambios": len(comparacion.cambios),
        "cambios": [asdict(cambio) for cambio in comparacion.cambios],
    }


def comparar_versiones(
    documento_corregido: DocumentoDatos,
    documento_anterior: Optional[DocumentoDatos],
) -> ComparacionVersiones:
    """Compara la versión corregida contra su versión anterior inmediata."""
    if not documento_anterior:
        return _sin_comparacion(documento_corregido, None, _MOTIVO_SIN_VERSION_ANTERIOR)

    snapshot_anterior = _snapshot_valido(documento_anterior)
    snapshot_corregido = _snapshot_valido(documento_corregido)
    if not snapshot_anterior or not snapshot_corregido:
        return _sin_comparacion(
            documento_corregido,
            documento_anterior,
            _motivo_snapshot_incompleto(snapshot_anterior, snapshot_corregido),
        )

    cambios = _detectar_cambios(
        snapshot_anterior,
        snapshot_corregido,
    )
    return ComparacionVersiones(
        disponible=True,
        motivo=None,
        version_anterior=documento_anterior.version_numero,
        version_corregida=documento_corregido.version_numero,
        moneda_anterior=_moneda_declaracion(snapshot_anterior),
        moneda_corregida=_moneda_declaracion(snapshot_corregido),
        documento_anterior_id=documento_anterior.id,
        documento_corregido_id=documento_corregido.id,
        cambios=cambios,
    )


def _sin_comparacion(
    documento_corregido: DocumentoDatos,
    documento_anterior: Optional[DocumentoDatos],
    motivo: str,
) -> ComparacionVersiones:
    return ComparacionVersiones(
        disponible=False,
        motivo=motivo,
        version_anterior=documento_anterior.version_numero if documento_anterior else 0,
        version_corregida=documento_corregido.version_numero,
        moneda_anterior=_moneda_declaracion(_snapshot_valido(documento_anterior)) if documento_anterior else None,
        moneda_corregida=_moneda_declaracion(_snapshot_valido(documento_corregido)),
        documento_anterior_id=documento_anterior.id if documento_anterior else None,
        documento_corregido_id=documento_corregido.id,
        cambios=[],
    )


def _snapshot_valido(documento: DocumentoDatos) -> Optional[Dict[str, Any]]:
    snapshot = documento.snapshot_datos
    if not isinstance(snapshot, dict) or not snapshot:
        return None
    return snapshot


def _motivo_snapshot_incompleto(
    snapshot_anterior: Optional[Dict[str, Any]],
    snapshot_corregido: Optional[Dict[str, Any]],
) -> str:
    if not snapshot_anterior and not snapshot_corregido:
        return _MOTIVO_SNAPSHOT_AMBAS
    if not snapshot_anterior:
        return _MOTIVO_SNAPSHOT_ANTERIOR
    return _MOTIVO_SNAPSHOT_CORREGIDO


def _moneda_declaracion(snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if not snapshot:
        return None
    moneda = snapshot.get("moneda_declaracion")
    if moneda is None:
        return None
    texto = str(moneda).strip()
    return texto or None


def _detectar_cambios(anterior: Dict[str, Any], corregido: Dict[str, Any]) -> List[CambioCampo]:
    presentes = (set(anterior) | set(corregido)) & CAMPOS_IDENTIFICABLES_PARA_CORRECION
    campos = [campo for campo in ETIQUETA_DE_CAMPO_EN_CORRECION if campo in presentes]
    return [
        CambioCampo(
            campo=campo,
            etiqueta=ETIQUETA_DE_CAMPO_EN_CORRECION.get(campo, campo),
            valor_anterior=_presentar(campo, anterior.get(campo), anterior),
            valor_corregido=_presentar(campo, corregido.get(campo), corregido),
        )
        for campo in campos
        if campo not in _CAMPOS_EXCLUIDOS
        and _normalizar(anterior.get(campo)) != _normalizar(corregido.get(campo))
    ]


def _normalizar(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        return " ".join(valor.split())
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(valor)


def _presentar(campo: str, valor: Any, snapshot: Dict[str, Any]) -> str:
    normalizado = _normalizar(valor)
    if not normalizado:
        return "Sin información"
    if campo in _CAMPOS_MONETARIOS:
        return _formatear_monto(valor, snapshot.get("moneda_declaracion"))
    if isinstance(valor, (list, dict)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return normalizado


def _formatear_monto(valor: Any, moneda: Any) -> str:
    return formatear_monto_monetario(valor, moneda) or _normalizar(valor)
