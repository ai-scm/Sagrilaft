"""Fixtures explícitos; sin OFAC real, PDFs ficticios, esperas ni acceso de red."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from domain.listas.contratos import (
    Advertencia, Candidato, Cobertura, Conclusion, ErrorConsulta, Estado,
    Implementacion, Motivo, ResultadoProveedorV2,
)
from domain.listas.puertos import Capacidades, ListasNoDisponibles, SolicitudProveedorV2


class SimuladorListasV2:
    def __init__(self, escenario: str):
        if escenario not in {"sin_coincidencias_v1", "coincidencia_v1", "parcial_v1", "error_v1"}:
            raise ValueError("Escenario desconocido")
        self.escenario = escenario

    def capacidades(self) -> Capacidades:
        return Capacidades(proveedor="simulador", adaptador_version="simulado-v1",
                           algoritmo_version="fixture-v1", criterios_busqueda=("nombre", "nombres_adicionales", "identificadores"),
                           tipos_identificador=("CC", "NIT", "PASAPORTE"),
                           version_explicita=False, evidencia_nativa=False, seleccion_fuentes=False)

    def consultar(self, solicitud: SolicitudProveedorV2) -> ResultadoProveedorV2:
        if solicitud.versiones:
            raise ValueError("El simulador no consulta versiones oficiales")
        criterio = solicitud.criterio
        soportados = self.capacidades().tipos_identificador
        if any(i.tipo not in soportados for i in criterio.identificadores):
            raise ValueError("Tipo de identificador no soportado por el escenario")
        ahora = datetime.now(timezone.utc)
        cobertura_id = uuid5(NAMESPACE_URL, f"{solicitud.consulta_id}/simulacion")
        error = self.escenario == "error_v1"
        parcial = self.escenario == "parcial_v1"
        candidato = self.escenario in {"coincidencia_v1", "parcial_v1"}
        cobertura = [Cobertura(id=cobertura_id, nombre_origen="Fixture ficticio",
                              version_declarada=self.escenario,
                              estado="FALLIDA" if error else "CONSULTADA")]
        if parcial:
            cobertura.append(Cobertura(id=uuid5(cobertura_id, "faltante"),
                                       nombre_origen="Fixture no disponible",
                                       version_declarada=self.escenario, estado="NO_DISPONIBLE"))
        candidatos = ()
        if candidato:
            valor = criterio.nombre or (criterio.nombres_adicionales[0] if criterio.nombres_adicionales
                                        else criterio.identificadores[0].valor)
            candidatos = (Candidato(
                id=uuid5(cobertura_id, "candidato"), cobertura_id=cobertura_id,
                uid_origen="fixture-001", tipo_sujeto="PERSONA",
                nombre_principal="Persona ficticia del escenario",
                motivos=(Motivo(campo="escenario", valor_consultado=valor,
                                valor_registro=self.escenario, metodo="PROVEEDOR"),),
                algoritmo_version="fixture-v1",
            ),)
        no_aplicados = tuple(Advertencia(codigo="CRITERIO_NO_APLICADO", descripcion=campo)
                            for campo in ("fecha_nacimiento", "fecha_expedicion", "nacionalidades", "ubicacion")
                            if getattr(criterio, campo))
        return ResultadoProveedorV2(
            consulta_id=solicitud.consulta_id, implementacion=Implementacion.SIMULADO,
            proveedor="simulador", estado_ejecucion=Estado.FALLIDA if error else (
                Estado.PARCIAL if parcial else Estado.COMPLETADA),
            conclusion_busqueda=Conclusion.NO_CONCLUYENTE if error or parcial else (
                Conclusion.CON_CANDIDATOS if candidato else Conclusion.SIN_CANDIDATOS),
            cobertura=tuple(cobertura), candidatos=candidatos,
            advertencias=(Advertencia(codigo="SIMULADO", descripcion=f"Datos ficticios: {self.escenario}"),),
            criterios_no_aplicados=no_aplicados, fecha_inicio=ahora, fecha_fin=ahora,
            error=ErrorConsulta(codigo="ERROR_SIMULADO", mensaje="Fallo del escenario de prueba",
                                correlacion_id=solicitud.correlacion_id, reintentable=False) if error else None,
        )

    def obtener_evidencia(self, referencia):
        raise ListasNoDisponibles("Sin evidencia nativa; el informe interno requiere persistencia F2")
