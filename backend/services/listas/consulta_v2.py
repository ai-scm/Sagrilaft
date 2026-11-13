"""Entrada interna F1 para ensayar el puerto. Sin endpoints ni cierre persistido.

F2 añadirá admisión/idempotencia durables; F3 conectará los circuitos HTTP.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from domain.listas.contratos import CrearConsultaV2, ResultadoProveedorV2
from domain.listas.puertos import ConsultorListasV2, SolicitudProveedorV2
from services.listas.politica_v2 import ActorListas, PoliticaListasV2


class EjecutorConsultaV2:
    def __init__(self, politica: PoliticaListasV2, consultor: ConsultorListasV2,
                 puede_acceder_expediente: Callable[[ActorListas, str], bool]):
        self.politica = politica
        self.consultor = consultor
        self.puede_acceder_expediente = puede_acceder_expediente

    def consultar(self, actor: ActorListas, solicitud: CrearConsultaV2,
                  consulta_id: UUID, correlacion_id: UUID) -> ResultadoProveedorV2:
        self.politica.consulta(actor, solicitud, self.puede_acceder_expediente)
        capacidades = self.consultor.capacidades()
        criterio = solicitud.criterio
        if criterio.nombre and "nombre" not in capacidades.criterios_busqueda:
            raise ValueError("Nombre no soportado")
        if criterio.nombres_adicionales and "nombres_adicionales" not in capacidades.criterios_busqueda:
            raise ValueError("Nombres adicionales no soportados")
        if criterio.identificadores and "identificadores" not in capacidades.criterios_busqueda:
            raise ValueError("Identificadores no soportados")
        if any(i.tipo not in capacidades.tipos_identificador for i in criterio.identificadores):
            raise ValueError("Tipo de identificador no soportado")
        parametros = {"escenario": self.politica.config.escenario} if self.politica.config.implementacion == "simulado" else {}
        manifiesto = {"implementacion": self.politica.config.implementacion,
                      "proveedor": capacidades.proveedor, "adaptador": capacidades.adaptador_version,
                      "algoritmo": capacidades.algoritmo_version, "parametros": parametros}
        huella = hashlib.sha256(json.dumps(manifiesto, sort_keys=True).encode()).hexdigest()
        return self.ejecutar_admitida(SolicitudProveedorV2(
            consulta_id=consulta_id, correlacion_id=correlacion_id, criterio=criterio,
            implementacion=self.politica.config.implementacion, proveedor=capacidades.proveedor,
            adaptador_version=capacidades.adaptador_version, algoritmo_version=capacidades.algoritmo_version,
            parametros=parametros, admitida_en=datetime.now(timezone.utc), huella_configuracion=huella))
    def ejecutar_admitida(self, solicitud: SolicitudProveedorV2) -> ResultadoProveedorV2:
        """Entrada del trabajador interno sobre una admisión ya autorizada y conservada."""
        resultado = self.consultor.consultar(solicitud)
        # Revalidar incluso un modelo construido por un adaptador que omita validación.
        resultado = ResultadoProveedorV2.model_validate(resultado.model_dump())
        if resultado.consulta_id != solicitud.consulta_id:
            raise ValueError("Respuesta de otra consulta")
        if resultado.proveedor != solicitud.proveedor:
            raise ValueError("Respuesta de otro proveedor")
        if resultado.implementacion.value != solicitud.implementacion.value:
            raise ValueError("Respuesta de otra implementación")
        return resultado
