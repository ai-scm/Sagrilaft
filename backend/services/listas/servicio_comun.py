"""Consultas del portal con historial durable; no decide riesgo ni estado comercial."""
from uuid import uuid4

from sqlalchemy import select, text, or_, and_

from domain.listas.contratos import CrearConsultaV2, SolicitudIdempotente, ConsultaV2
from domain.listas.contratos_busqueda import CrearConsultaBusqueda, ConsultaBusquedaF6
from domain.listas.puertos import ListasNoDisponibles
from infrastructure.persistencia.models import Formulario, ResultadoValidacion
from infrastructure.persistencia.modelos_listas import ConsultaLista, CoincidenciaLista, EvidenciaConsulta, TrabajoConsulta, RevisionCumplimiento
from infrastructure.persistencia.modelos_grupos_listas import GrupoConsultaLista
from infrastructure.persistencia.repositorios.consultas_listas import RepositorioConsultasListas
from services.listas.informes import calcular_huella
from services.listas.politica_v2 import PoliticaListasV2


class ServicioComunListas:
    def __init__(self, sesiones, politica: PoliticaListasV2, custodia, actor, contrapartes, entorno="development"):
        self.sesiones, self.politica, self.actor = sesiones, politica, actor
        self.contrapartes = frozenset(contrapartes)
        self.custodia = custodia
        self.entorno = entorno
        self.repositorio = self._repositorio(sesiones)

    def _repositorio(self, sesiones):
        return RepositorioConsultasListas(sesiones, self.politica, self.custodia,
            self.puede_acceder_expediente, self.puede_acceder_consulta, self._sin_archivos)

    @staticmethod
    def _sin_archivos(*_):
        raise ListasNoDisponibles("El buscador por archivos no está disponible")

    def puede_acceder_expediente(self, _actor, expediente_id):
        with self.sesiones() as sesion:
            expediente = sesion.get(Formulario, expediente_id)
            return expediente is not None and expediente.tipo_contraparte in self.contrapartes

    def puede_acceder_consulta(self, actor, consulta_id):
        with self.sesiones() as sesion:
            consulta = sesion.get(ConsultaLista, consulta_id)
            return consulta is not None and consulta.expediente_id is not None and self.puede_acceder_expediente(actor, consulta.expediente_id)

    def exigir_expediente(self, expediente_id):
        if not self.puede_acceder_expediente(self.actor, expediente_id):
            raise LookupError("Expediente no disponible")

    def exigir_consulta(self, consulta_id):
        if not self.puede_acceder_consulta(self.actor, consulta_id):
            raise LookupError("Consulta no disponible")

    def _manifiesto(self):
        if self.politica.config.implementacion != "simulado":
            raise ListasNoDisponibles("Esta entrega permite únicamente consultas simuladas")
        return {"implementacion": "simulado", "proveedor": "simulador", "adaptador": "simulado-v1",
                "algoritmo": "fixture-v1", "escenario": self.politica.config.escenario}

    def crear(self, expediente_id, solicitud: CrearConsultaV2, clave):
        self.exigir_expediente(expediente_id)
        self.actor.exigir("listas.consultar")
        if solicitud.contexto.tipo != "EXPEDIENTE" or solicitud.contexto.expediente_id != expediente_id:
            raise ValueError("El contexto debe corresponder al expediente de la ruta")
        if isinstance(solicitud, CrearConsultaBusqueda):
            from services.listas.servicio_archivos_portal import crear_individual
            return crear_individual(self, solicitud, clave)
        if any(i.tipo not in {"CC", "NIT", "PASAPORTE"} for i in solicitud.criterio.identificadores):
            raise ValueError("Tipo de identificador no soportado por el simulador")
        return self.repositorio.admitir(self.actor, SolicitudIdempotente(clave=clave, solicitud=solicitud), "simulador", self._manifiesto())

    def crear_grupo(self, expediente_id, clave):
        self.exigir_expediente(expediente_id)
        self.actor.exigir("listas.consultar")
        huella = calcular_huella({"expediente": expediente_id, "operacion": "ambos_sujetos_v1"})
        with self.sesiones.begin() as sesion:
            # Serializa solo esta identidad/expediente/clave y se libera con el commit.
            bloqueo = calcular_huella([self.actor.issuer, self.actor.sub, expediente_id, clave])
            sesion.execute(text("SELECT pg_advisory_xact_lock(:clave)"), {"clave": int(bloqueo[:15], 16)})
            anterior = sesion.scalar(select(GrupoConsultaLista).where(GrupoConsultaLista.actor_emisor == self.actor.issuer,
                GrupoConsultaLista.actor_sujeto == self.actor.sub, GrupoConsultaLista.expediente_id == expediente_id,
                GrupoConsultaLista.clave == clave))
            if anterior:
                return anterior.respuesta
            if self.politica.config.implementacion == "archivos":
                from services.listas.servicio_archivos_portal import crear_grupo
                return crear_grupo(self, expediente_id, clave, sesion, uuid4())
            manifiesto = self._manifiesto()
            expediente = sesion.get(Formulario, expediente_id)
            grupo_id = uuid4()
            solicitudes, omitidos = [], []
            for rol, nombre, documento, tipo in (
                ("CONTRAPARTE", expediente.razon_social, expediente.numero_identificacion, expediente.tipo_identificacion),
                ("REPRESENTANTE", expediente.nombre_representante, expediente.numero_doc_representante, expediente.tipo_doc_representante),
            ):
                criterio = {"tipo_sujeto": "NO_DETERMINADO" if rol == "CONTRAPARTE" else "PERSONA"}
                if nombre and nombre.strip():
                    criterio["nombre"] = nombre.strip()
                if documento and tipo in {"CC", "NIT", "PASAPORTE"}:
                    criterio["identificadores"] = [{"tipo": tipo, "valor": documento}]
                if len(criterio) == 1:
                    omitidos.append({"sujeto_rol": rol, "motivo": "No hay criterios utilizables por el simulador"})
                    continue
                solicitudes.append(CrearConsultaV2(version_contrato="2.0", contexto={"tipo": "EXPEDIENTE",
                    "expediente_id": expediente_id, "sujeto_rol": rol}, criterio=criterio))
            # El grupo se inserta terminado; cada hijo lo referencia en esta misma transacción.
            respuesta = {"grupo_id": str(grupo_id), "consultas": [], "no_consultados": omitidos}
            # La respuesta definitiva se calcula con ids reservados por el repositorio.
            grupo = GrupoConsultaLista(id=grupo_id, actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub,
                expediente_id=expediente_id, clave=clave, huella=huella, respuesta={})
            # Diferir FK para poder insertar el grupo ya completo al final.
            sesion.execute(text("SET CONSTRAINTS fk_consulta_grupo DEFERRED"))
            for solicitud in solicitudes:
                identificador = self.repositorio.admitir(self.actor,
                    SolicitudIdempotente(clave=f"grupo:{grupo_id}:{solicitud.contexto.sujeto_rol}", solicitud=solicitud),
                    "simulador", manifiesto, grupo_id=grupo_id, sesion_actual=sesion)
                respuesta["consultas"].append({"consulta_id": str(identificador), "sujeto_rol": solicitud.contexto.sujeto_rol})
            grupo.respuesta = respuesta
            sesion.add(grupo)
            return respuesta

    def detalle(self, consulta_id):
        self.actor.exigir("listas.ver_evidencias")
        self.exigir_consulta(consulta_id)
        with self.sesiones() as sesion:
            consulta = sesion.get(ConsultaLista, consulta_id)
            trabajo = sesion.scalar(select(TrabajoConsulta).where(TrabajoConsulta.consulta_id == consulta_id))
            evidencias = list(sesion.scalars(select(EvidenciaConsulta).where(EvidenciaConsulta.consulta_id == consulta_id)))
            resultado = consulta.resultado or {"consulta_id": consulta.id, "implementacion": consulta.implementacion,
                "version_contrato": consulta.version_contrato,
                "proveedor": consulta.proveedor, "estado_ejecucion": consulta.estado, "conclusion_busqueda": consulta.conclusion,
                "cobertura": [], "fecha_inicio": consulta.creado_en, "fecha_fin": consulta.finalizada_en,
                "advertencias": [{"codigo": "SIMULADO", "descripcion": "Datos ficticios"}] if consulta.implementacion == "simulado" else []}
            if not consulta.resultado and trabajo.error:
                resultado["error"] = {"codigo": trabajo.error, "mensaje": "La consulta no pudo completarse",
                                      "correlacion_id": consulta.id, "reintentable": False}
            modelo = ConsultaBusquedaF6 if consulta.version_contrato == "2.1" else ConsultaV2
            datos = modelo(**resultado, contexto={"tipo": "EXPEDIENTE", "expediente_id": consulta.expediente_id,
                "sujeto_rol": consulta.sujeto_rol, "motivo": consulta.motivo}, criterio=consulta.criterio_original,
                grupo_id=consulta.grupo_id, fase=trabajo.fase,
                **({"trazabilidad": consulta.manifiesto.get("busqueda")} if consulta.version_contrato == "2.1" else {}),
                evidencias=[{"id": e.id, "tipo": e.tipo, "estado": "DISPONIBLE", "sha256": e.huella,
                    "creada_en": e.creado_en, "generador_version": e.version_generador} for e in evidencias])
            revisiones = list(sesion.scalars(select(RevisionCumplimiento).where(RevisionCumplimiento.consulta_id == consulta_id)
                                            .order_by(RevisionCumplimiento.creado_en, RevisionCumplimiento.id)))
            return {"consulta": datos.model_dump(mode="json"), "revisiones": [{"id": str(r.id), "resultado": r.resultado,
                "justificacion": r.justificacion, "coincidencia_id": str(r.coincidencia_id) if r.coincidencia_id else None,
                "revision_previa_id": str(r.revision_previa_id) if r.revision_previa_id else None,
                "creado_en": r.creado_en.isoformat(), "actor_sujeto": r.actor_sujeto, "actor_emisor": r.actor_emisor} for r in revisiones]}

    def historial(self, expediente_id, antes=None, limite=20):
        self.actor.exigir("listas.ver_evidencias")
        self.exigir_expediente(expediente_id)
        with self.sesiones() as sesion:
            sentencia = select(ConsultaLista).where(ConsultaLista.expediente_id == expediente_id)
            if antes:
                ultima = sesion.get(ConsultaLista, antes)
                if not ultima or ultima.expediente_id != expediente_id:
                    raise ValueError("Cursor no válido para el expediente")
                sentencia = sentencia.where(or_(ConsultaLista.creado_en < ultima.creado_en,
                    and_(ConsultaLista.creado_en == ultima.creado_en, ConsultaLista.id < ultima.id)))
            filas = list(sesion.scalars(sentencia.order_by(ConsultaLista.creado_en.desc(), ConsultaLista.id.desc()).limit(limite + 1)))
            expediente = sesion.get(Formulario, expediente_id)
            return {"consultas": [{"consulta_id": str(c.id), "estado": c.estado, "conclusion": c.conclusion,
                    "sujeto_rol": c.sujeto_rol, "creado_en": c.creado_en.isoformat()} for c in filas[:limite]],
                "siguiente": str(filas[limite-1].id) if len(filas) > limite else None,
                "legado": {"validaciones": [{"campo": r.campo, "resultado_original": r.resultado, "detalle": r.detalle}
                    for r in sesion.scalars(select(ResultadoValidacion).where(ResultadoValidacion.formulario_id == expediente_id,
                        ResultadoValidacion.tipo == "lista_cautela").order_by(ResultadoValidacion.id))],
                           "reporte_id": expediente.sagrilaft_reporte_id, "evidencia_disponible": False,
                           "descripcion": "Referencia heredada sin custodia v2; no se consulta al proveedor"}}

    def evidencia(self, consulta_id, evidencia_id):
        self.actor.exigir("listas.ver_evidencias")
        self.exigir_consulta(consulta_id)
        with self.sesiones() as sesion:
            evidencia = sesion.get(EvidenciaConsulta, evidencia_id)
            if not evidencia or evidencia.consulta_id != consulta_id or evidencia.tipo != "INFORME_INTERNO":
                raise LookupError("Evidencia no disponible")
        return self.repositorio.leer_informe(self.actor, consulta_id)

    def revisar(self, consulta_id, resultado, justificacion, coincidencia_id=None, revision_previa_id=None):
        self.actor.exigir("listas.revisar")
        self.exigir_consulta(consulta_id)
        with self.sesiones() as sesion:
            for modelo, identificador in ((CoincidenciaLista, coincidencia_id), (RevisionCumplimiento, revision_previa_id)):
                if identificador:
                    objeto = sesion.get(modelo, identificador)
                    if objeto is None or objeto.consulta_id != consulta_id:
                        raise LookupError("Referencia de revisión no disponible")
        return self.repositorio.revisar(self.actor, consulta_id, resultado, justificacion, coincidencia_id, revision_previa_id)
