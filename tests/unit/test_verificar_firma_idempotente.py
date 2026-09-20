"""
Verifica que verificar_estado_firma() sea idempotente cuando el webhook de
ZohoSign le gana la carrera: ambos caminos toman el mismo lock de fila
(bloquear=True → SELECT ... FOR UPDATE, ver infrastructure/persistencia/
repositorios/firma.py y _base.py) por lo que no hay riesgo de datos
corruptos — el problema real era que la verificación manual rechazaba con
400 un formulario que ya había llegado al estado deseado (FIRMADO).
"""

import pytest

from domain.excepciones import FormularioNoEditableError
from domain.formulario.entidades import FormularioDatos
from domain.formulario.tipos import EstadoFormulario
from services.firma.firma_service import FirmaService


class _RepoFirmaFake:
    """Fake mínimo de RepositorioFirma — solo lo que usa verificar_estado_firma."""

    def __init__(self, formulario: FormularioDatos):
        self._formulario = formulario
        self.actualizado_con: dict | None = None

    def obtener_formulario(self, formulario_id: str, bloquear: bool = False) -> FormularioDatos:
        return self._formulario

    def actualizar_formulario(self, formulario_id: str, campos: dict) -> None:
        self.actualizado_con = campos


def _crear_servicio(formulario: FormularioDatos) -> tuple[FirmaService, _RepoFirmaFake]:
    repo = _RepoFirmaFake(formulario)
    zoho_mock = object()  # no debe usarse en el camino idempotente
    storage_mock = object()  # idem
    servicio = FirmaService(
        repo=repo,
        zoho=zoho_mock,
        storage=storage_mock,
        webhook_secret="secret-test",
    )
    return servicio, repo


def _formulario(estado: str, zoho_request_id: str | None = "zoho-req-1") -> FormularioDatos:
    return FormularioDatos(
        id="f-1",
        codigo_peticion="SAG-00000001",
        estado=estado,
        zoho_request_id=zoho_request_id,
    )


def test_verificar_firma_ya_firmado_no_lanza_400_es_idempotente():
    """Reproduce la carrera del reporte: el webhook ya transicionó a FIRMADO
    antes de que el frontend llame a verificar-firma. Debe devolver éxito,
    no FormularioNoEditableError (que el endpoint mapea a 400)."""
    formulario = _formulario(EstadoFormulario.FIRMADO.value)
    servicio, repo = _crear_servicio(formulario)

    resultado = servicio.verificar_estado_firma("f-1")

    assert resultado == {"estado_zoho": "completed", "estado": EstadoFormulario.FIRMADO.value}
    # No debe intentar escribir en BD ni tocar ZohoSign — ya está resuelto.
    assert repo.actualizado_con is None


def test_verificar_firma_en_otro_estado_sigue_rechazando_con_400():
    """El fix es específico para FIRMADO — otros estados inválidos (ej. nunca
    se envió a firma) siguen siendo un error real, no una carrera legítima."""
    formulario = _formulario(EstadoFormulario.VALIDADO.value, zoho_request_id=None)
    servicio, _ = _crear_servicio(formulario)

    with pytest.raises(FormularioNoEditableError):
        servicio.verificar_estado_firma("f-1")
