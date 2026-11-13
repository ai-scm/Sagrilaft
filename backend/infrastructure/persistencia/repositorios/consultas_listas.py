"""Historial, admisión y trabajos durables. No importa ni busca archivos OFAC."""
from contextlib import nullcontext
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from domain.listas.contratos import ContextoExpediente, ResultadoProveedorV2, SolicitudIdempotente
from domain.listas.contratos_busqueda import ResultadoBusquedaF6
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia, TrabajoNoVigente, VersionNoDisponible
from infrastructure.persistencia.modelos_listas import (
    ArchivoFuente, BorradorConsulta, CoincidenciaLista, ConsultaFuente, ConsultaLista,
    EventoConsulta, EvidenciaConsulta, FuenteLista, FuenteVersionActiva, HallazgoProveedor,
    PoliticaListas, ProgresoConsultaExterna, RevisionCumplimiento, RitmoProveedor, TrabajoConsulta, VersionFuente,
)
from services.listas.informes import calcular_huella, generar_informe_pdf, version_informe
from services.listas.politica_v2 import ActorListas, PoliticaListasV2


@dataclass(frozen=True)
class ProgresoExterno:
    consulta_id: UUID
    etapa: str
    jobid: str | None
    reporte_id: str | None
    recargas: int
    vence_en: datetime
    huella_respuesta: str | None
    respuesta_filtrada: dict | None


@dataclass(frozen=True)
class ConcesionConsulta:
    consulta_id: UUID
    numero_control: int
    fase: str


class RepositorioConsultasListas:
    def __init__(self, sesiones, politica: PoliticaListasV2, custodia, puede_acceder_expediente,
                 puede_acceder_consulta, verificar_vigencia, reloj=None, generar_informe=generar_informe_pdf):
        self.sesiones = sesiones
        self.politica = politica
        self.custodia = custodia
        self.puede_acceder_expediente = puede_acceder_expediente
        self.puede_acceder_consulta = puede_acceder_consulta
        self.verificar_vigencia = verificar_vigencia
        self.reloj = reloj or (lambda: datetime.now(timezone.utc))
        self.generar_informe = generar_informe

    def admitir(self, actor: ActorListas, peticion: SolicitudIdempotente, proveedor: str,
                manifiesto: dict, fuentes_requeridas: tuple[UUID, ...] = (), politica_id: UUID | None = None, grupo_id: UUID | None = None, sesion_actual=None,
                preparar_admision=None, criterio_efectivo=None) -> UUID:
        solicitud = peticion.solicitud
        self.politica.consulta(actor, solicitud, self.puede_acceder_expediente)
        modo = self.politica.config.implementacion
        if modo == "archivos" and preparar_admision is None and (not fuentes_requeridas or politica_id is None):
            raise VersionNoDisponible("Archivos requiere fuentes y política registradas")
        expediente = solicitud.contexto if isinstance(solicitud.contexto, ContextoExpediente) else None
        ambito = f"expediente:{expediente.expediente_id}:{expediente.sujeto_rol}" if expediente else "independiente"
        identificador = uuid4()
        with (nullcontext(sesion_actual) if sesion_actual is not None else self.sesiones.begin()) as sesion:
            error_admision, coberturas_nuevas = None, []
            if solicitud.version_contrato == "2.1":
                bloqueo = calcular_huella(["admision-21", actor.issuer, actor.sub, ambito, peticion.clave])
                from sqlalchemy import text
                sesion.execute(text("SELECT pg_advisory_xact_lock(:clave)"), {"clave": int(bloqueo[:15], 16)})
                anterior = sesion.scalar(select(ConsultaLista).where(ConsultaLista.actor_emisor == actor.issuer,
                    ConsultaLista.actor_sujeto == actor.sub, ConsultaLista.ambito_idempotencia == ambito,
                    ConsultaLista.clave_idempotencia == peticion.clave))
                if anterior:
                    if anterior.huella_peticion != peticion.hash_cuerpo:
                        raise ConflictoListas("La clave corresponde a otros criterios de consulta")
                    return anterior.id
                if modo != "archivos" or preparar_admision is None:
                    raise VersionNoDisponible("El contrato 2.1 requiere admisión por archivos")
                try:
                    manifiesto, coberturas_nuevas = preparar_admision(sesion, identificador)
                except (VersionNoDisponible, ErrorIntegridadEvidencia) as error:
                    error_admision = error
                    politica_id = None
                    fallido = {k: v for k, v in manifiesto.items() if k != "huella"}
                    fallido["error_fijacion"] = str(error)
                    manifiesto = {**fallido, "huella": calcular_huella(fallido)}
            sentencia = insert(ConsultaLista).values(
                id=identificador, grupo_id=grupo_id, creado_en=self.reloj(), actor_emisor=actor.issuer, actor_sujeto=actor.sub,
                expediente_id=expediente.expediente_id if expediente else None,
                sujeto_rol=expediente.sujeto_rol if expediente else None, motivo=solicitud.contexto.motivo,
                ambito_idempotencia=ambito, clave_idempotencia=peticion.clave, huella_peticion=peticion.hash_cuerpo,
                implementacion=modo, proveedor=proveedor, version_contrato=solicitud.version_contrato,
                criterio_original=(criterio_efectivo or solicitud.criterio).model_dump(mode="json"), manifiesto=manifiesto,
                politica_id=politica_id, estado="PENDIENTE",
            ).on_conflict_do_nothing(constraint="uq_consulta_peticion").returning(ConsultaLista.id)
            creado = sesion.execute(sentencia).scalar_one_or_none()
            if creado is None:
                existente = sesion.execute(select(ConsultaLista).where(ConsultaLista.actor_emisor == actor.issuer,
                    ConsultaLista.actor_sujeto == actor.sub, ConsultaLista.ambito_idempotencia == ambito,
                    ConsultaLista.clave_idempotencia == peticion.clave)).scalar_one()
                if existente.huella_peticion != peticion.hash_cuerpo:
                    raise ConflictoListas("La clave corresponde a otros criterios de consulta")
                return existente.id
            try:
                if error_admision:
                    raise VersionNoDisponible("No se pudo fijar la cobertura requerida") from error_admision
                if solicitud.version_contrato == "2.1":
                    sesion.add_all(coberturas_nuevas)
                elif modo == "archivos":
                    self._fijar_versiones(sesion, identificador, fuentes_requeridas, politica_id)
            except VersionNoDisponible as error:
                consulta = sesion.get(ConsultaLista, identificador)
                sesion.add(ConsultaFuente(consulta_id=identificador, nombre_origen="Cobertura requerida no disponible",
                    estado="NO_DISPONIBLE", requerida=True, detalle={"fuentes_requeridas": [str(f) for f in fuentes_requeridas]}))
                sesion.flush()
                consulta.estado = "FALLIDA"
                consulta.conclusion = "NO_CONCLUYENTE"
                consulta.finalizada_en = self.reloj()
                sesion.add(TrabajoConsulta(consulta_id=identificador, fase="FINALIZADA", numero_control=0,
                                           error="FUENTE_NO_DISPONIBLE"))
                self._evento(sesion, identificador, "ADMISION_FALLIDA", actor, {"motivo": str(error)})
            else:
                sesion.add(TrabajoConsulta(consulta_id=identificador, fase="ADMISION", numero_control=0))
                self._evento(sesion, identificador, "ADMITIDA", actor, {})
        return identificador

    def _fijar_versiones(self, sesion, consulta_id, fuentes, politica_id):
        punteros = list(sesion.execute(select(FuenteVersionActiva).where(FuenteVersionActiva.fuente_id.in_(fuentes))
                        .order_by(FuenteVersionActiva.fuente_id).with_for_update(read=True)).scalars())
        if len(punteros) != len(set(fuentes)) or any(p.version_id is None for p in punteros):
            raise VersionNoDisponible("Una fuente requerida no tiene versión activa")
        versiones = {v.id: v for v in sesion.execute(select(VersionFuente).where(VersionFuente.id.in_([p.version_id for p in punteros]))
                     .order_by(VersionFuente.id).with_for_update(read=True)).scalars()}
        politica = sesion.get(PoliticaListas, politica_id)
        if politica is None:
            raise VersionNoDisponible("Política inexistente")
        for puntero in punteros:
            version = versiones[puntero.version_id]
            if version.estado != "VALIDA":
                raise VersionNoDisponible("La versión activa está bloqueada")
            self.verificar_vigencia(sesion, version, politica)
        for puntero in punteros:
            version = versiones[puntero.version_id]
            fuente = sesion.get(FuenteLista, puntero.fuente_id)
            sesion.add(ConsultaFuente(consulta_id=consulta_id, fuente_id=puntero.fuente_id,
                version_id=version.id, revision_activa=puntero.revision, nombre_origen=fuente.nombre,
                estado="PENDIENTE", requerida=True, detalle={"huella_contenido": version.huella_contenido,
                    "fuente_codigo": fuente.codigo, "fuente_nombre": fuente.nombre,
                    "version_importador": version.version_importador, "version_normalizador": version.version_normalizador,
                    "esquema_id": str(version.esquema_id),
                    "manifiesto": version.manifiesto, "publicada_en": version.publicada_en,
                    "politica_id": str(politica.id), "admitida_en": self.reloj().isoformat()}))

    def reclamar(self, consulta_id: UUID, duracion_segundos: int = 120) -> ConcesionConsulta | None:
        """Devuelve None si una llamada externa vencida debe quedar indeterminada."""
        if not 1 <= duracion_segundos <= 3600:
            raise ValueError("Duración de concesión fuera de rango")
        with self.sesiones.begin() as sesion:
            trabajo = self._trabajo_bloqueado(sesion, consulta_id)
            consulta = sesion.get(ConsultaLista, consulta_id)
            ahora = self.reloj()
            if consulta.estado not in {"PENDIENTE", "EN_CURSO"}:
                raise TrabajoNoVigente("Consulta ya finalizada")
            if trabajo.concesion_hasta and trabajo.concesion_hasta > ahora:
                raise TrabajoNoVigente("Otro ejecutor conserva la concesión")
            borrador = sesion.execute(select(BorradorConsulta.id).where(BorradorConsulta.consulta_id == consulta_id)).first()
            # Una consulta externa se retoma solo si su progreso prueba que no quedó un lanzamiento
            # a medias: sin progreso, o en LANZANDO, el efecto en el proveedor es desconocido.
            etapa = sesion.scalar(select(ProgresoConsultaExterna.etapa).where(ProgresoConsultaExterna.consulta_id == consulta_id))
            if (consulta.implementacion == "externo" and trabajo.numero_control > 0 and not borrador
                    and etapa in {None, "LANZANDO"}):
                consulta.estado = "INDETERMINADA"
                consulta.conclusion = "NO_CONCLUYENTE"
                consulta.finalizada_en = ahora
                trabajo.fase = "FINALIZADA"
                trabajo.concesion_hasta = None
                trabajo.error = "EFECTO_EXTERNO_DESCONOCIDO"
                self._evento(sesion, consulta.id, "EFECTO_EXTERNO_DESCONOCIDO",
                             ActorListas(consulta.actor_emisor, consulta.actor_sujeto, frozenset()),
                             {"numero_control": trabajo.numero_control})
                return None
            trabajo.numero_control += 1
            trabajo.ultimo_latido = ahora
            trabajo.concesion_hasta = ahora + timedelta(seconds=duracion_segundos)
            trabajo.fase = "PREPARANDO_EVIDENCIA" if borrador else "BUSQUEDA"
            consulta.estado = "EN_CURSO"
            return ConcesionConsulta(consulta_id, trabajo.numero_control, trabajo.fase)

    def renovar(self, concesion: ConcesionConsulta, duracion_segundos: int = 120):
        if not 1 <= duracion_segundos <= 3600:
            raise ValueError("Duración de concesión fuera de rango")
        with self.sesiones.begin() as sesion:
            trabajo = self._exigir_concesion(sesion, concesion)
            trabajo.ultimo_latido = self.reloj()
            trabajo.concesion_hasta = self.reloj() + timedelta(seconds=duracion_segundos)

    def posponer(self, concesion: ConcesionConsulta, segundos: float):
        """Deja la consulta en curso y la libera hasta el próximo intento; otro ejecutor podrá retomarla."""
        if not 0 < segundos <= 3600:
            raise ValueError("Espera fuera de rango")
        with self.sesiones.begin() as sesion:
            trabajo = self._exigir_concesion(sesion, concesion)
            trabajo.ultimo_latido = self.reloj()
            trabajo.concesion_hasta = self.reloj() + timedelta(seconds=segundos)

    def progreso_externo(self, consulta_id: UUID) -> "ProgresoExterno | None":
        with self.sesiones() as sesion:
            fila = sesion.scalar(select(ProgresoConsultaExterna).where(ProgresoConsultaExterna.consulta_id == consulta_id))
            return ProgresoExterno(**{c.name: getattr(fila, c.name) for c in fields(ProgresoExterno)}) if fila else None

    def guardar_progreso(self, concesion: ConcesionConsulta, evento: str | None = None, **cambios):
        """Registra la etapa del protocolo externo; se confirma antes de cada llamada al proveedor."""
        permitidos = {c.name for c in fields(ProgresoExterno)} - {"consulta_id"}
        if set(cambios) - permitidos:
            raise ValueError("Campo de progreso desconocido")
        with self.sesiones.begin() as sesion:
            self._exigir_concesion(sesion, concesion)
            fila = sesion.scalar(select(ProgresoConsultaExterna).where(ProgresoConsultaExterna.consulta_id == concesion.consulta_id)
                                 .with_for_update())
            if fila is None:
                fila = ProgresoConsultaExterna(consulta_id=concesion.consulta_id, recargas=0)
                sesion.add(fila)
            for campo, valor in cambios.items():
                setattr(fila, campo, valor)
            fila.actualizado_en = self.reloj()
            if evento:
                consulta = sesion.get(ConsultaLista, concesion.consulta_id)
                self._evento(sesion, consulta.id, evento, ActorListas(consulta.actor_emisor, consulta.actor_sujeto, frozenset()),
                             {"etapa": fila.etapa})

    def reservar_turno(self, proveedor: str, intervalo_segundos: float) -> float:
        """Reparte lanzamientos entre ejecutores: 0 si este puede lanzar ya; si no, segundos de espera."""
        with self.sesiones.begin() as sesion:
            sesion.execute(insert(RitmoProveedor).values(proveedor=proveedor, ultimo_lanzamiento=datetime(2000, 1, 1, tzinfo=timezone.utc))
                           .on_conflict_do_nothing(index_elements=["proveedor"]))
            ritmo = sesion.execute(select(RitmoProveedor).where(RitmoProveedor.proveedor == proveedor).with_for_update()).scalar_one()
            ahora = self.reloj()
            disponible = ritmo.ultimo_lanzamiento + timedelta(seconds=intervalo_segundos)
            if disponible > ahora:
                return (disponible - ahora).total_seconds()
            ritmo.ultimo_lanzamiento = ahora
            return 0.0

    def agregar_evidencia_proveedor(self, concesion: ConcesionConsulta, tipo: str, objeto, tipo_contenido: str,
                                    version_generador: str) -> UUID:
        """Evidencia entregada por el proveedor (p. ej. su PDF), ya custodiada."""
        if tipo not in {"PDF_PROVEEDOR", "RESPUESTA_ORIGINAL"}:
            raise ValueError("Tipo de evidencia de proveedor no válido")
        with self.sesiones.begin() as sesion:
            self._exigir_concesion(sesion, concesion)
            existente = sesion.scalar(select(EvidenciaConsulta.id).where(EvidenciaConsulta.consulta_id == concesion.consulta_id,
                                                                         EvidenciaConsulta.tipo == tipo))
            if existente:
                return existente
            identificador = uuid4()
            sesion.add(EvidenciaConsulta(id=identificador, consulta_id=concesion.consulta_id, tipo=tipo, clave=objeto.clave,
                huella=objeto.huella, tamano_bytes=objeto.tamano_bytes, tipo_contenido=tipo_contenido,
                version_generador=version_generador))
            return identificador

    def guardar_borrador(self, concesion: ConcesionConsulta, resultado: ResultadoProveedorV2):
        resultado = self._validar_resultado(resultado.model_dump())
        if resultado.consulta_id != concesion.consulta_id or resultado.fecha_fin is None:
            raise ConflictoListas("Resultado no corresponde al trabajo o no es terminal")
        datos = resultado.model_dump(mode="json")
        huella = calcular_huella(datos)
        with self.sesiones.begin() as sesion:
            trabajo = self._exigir_concesion(sesion, concesion)
            consulta = sesion.get(ConsultaLista, concesion.consulta_id)
            if resultado.version_contrato != consulta.version_contrato:
                raise ConflictoListas("Resultado de otra versión de contrato")
            self._validar_resultado_fijado(sesion, consulta, resultado)
            if resultado.implementacion.value != consulta.implementacion or resultado.proveedor != consulta.proveedor:
                raise ConflictoListas("Resultado de otra implementación o proveedor")
            borrador = sesion.execute(select(BorradorConsulta).where(BorradorConsulta.consulta_id == consulta.id)).scalar_one_or_none()
            if borrador:
                if borrador.huella != huella:
                    raise ConflictoListas("No se sustituye un resultado ya conservado")
            else:
                sesion.add(BorradorConsulta(consulta_id=consulta.id, resultado=datos, huella=huella))
            trabajo.fase = "PREPARANDO_EVIDENCIA"

    def preparar_informe(self, concesion: ConcesionConsulta):
        with self.sesiones() as sesion:
            borrador = sesion.execute(select(BorradorConsulta).where(BorradorConsulta.consulta_id == concesion.consulta_id)).scalar_one()
            consulta = sesion.get(ConsultaLista, concesion.consulta_id)
            if calcular_huella(borrador.resultado) != borrador.huella:
                raise ConflictoListas("El borrador no coincide con su huella")
            if borrador.informe_clave:
                return self.custodia.leer(borrador.informe_clave, borrador.informe_huella, borrador.informe_tamano)
            datos = {"criterio": consulta.criterio_original, "manifiesto": consulta.manifiesto,
                     "contexto": {"expediente_id": consulta.expediente_id, "sujeto_rol": consulta.sujeto_rol,
                                  "motivo": consulta.motivo},
                     "resultado": borrador.resultado, "version_generador": version_informe(borrador.resultado)}
        contenido = self.generar_informe(datos)
        objeto = self.custodia.guardar(contenido)
        with self.sesiones.begin() as sesion:
            self._exigir_concesion(sesion, concesion)
            borrador = sesion.execute(select(BorradorConsulta).where(BorradorConsulta.consulta_id == concesion.consulta_id)).scalar_one()
            if borrador.informe_clave is None:
                borrador.informe_clave = objeto.clave
                borrador.informe_huella = objeto.huella
                borrador.informe_tamano = objeto.tamano_bytes
        return contenido

    def cerrar(self, concesion: ConcesionConsulta) -> UUID:
        # Repetir un cierre confirmado devuelve la misma evidencia, sin escribir otra.
        with self.sesiones() as sesion:
            trabajo = sesion.execute(select(TrabajoConsulta).where(TrabajoConsulta.consulta_id == concesion.consulta_id)).scalar_one()
            if trabajo.fase == "FINALIZADA":
                if trabajo.numero_control != concesion.numero_control:
                    raise TrabajoNoVigente("El cierre pertenece a otra concesión")
                evidencia = sesion.execute(select(EvidenciaConsulta.id).where(EvidenciaConsulta.consulta_id == concesion.consulta_id,
                    EvidenciaConsulta.tipo == "INFORME_INTERNO")).scalar_one_or_none()
                if evidencia:
                    return evidencia
                raise TrabajoNoVigente("Trabajo finalizado sin informe")
        # La lectura e integridad del archivo se comprueban fuera de los bloqueos SQL.
        with self.sesiones() as sesion:
            borrador = sesion.execute(select(BorradorConsulta).where(BorradorConsulta.consulta_id == concesion.consulta_id)).scalar_one()
            if not borrador.informe_clave:
                raise ConflictoListas("Informe pendiente de custodia")
            self.custodia.leer(borrador.informe_clave, borrador.informe_huella, borrador.informe_tamano)
        with self.sesiones.begin() as sesion:
            trabajo = self._trabajo_bloqueado(sesion, concesion.consulta_id)
            if trabajo.fase == "FINALIZADA" and trabajo.numero_control == concesion.numero_control:
                return sesion.execute(select(EvidenciaConsulta.id).where(EvidenciaConsulta.consulta_id == concesion.consulta_id,
                    EvidenciaConsulta.tipo == "INFORME_INTERNO")).scalar_one()
            trabajo = self._exigir_concesion(sesion, concesion)
            consulta = sesion.execute(select(ConsultaLista).where(ConsultaLista.id == concesion.consulta_id).with_for_update()).scalar_one()
            borrador = sesion.execute(select(BorradorConsulta).where(BorradorConsulta.consulta_id == consulta.id)).scalar_one()
            resultado = self._validar_resultado(borrador.resultado)
            if resultado.version_contrato != consulta.version_contrato:
                raise ConflictoListas("Contrato del borrador incompatible con admisión")
            self._validar_resultado_fijado(sesion, consulta, resultado)
            if calcular_huella(borrador.resultado) != borrador.huella:
                raise ConflictoListas("Borrador alterado")
            self._guardar_resultados(sesion, consulta, resultado)
            evidencia_id = uuid4()
            sesion.add(EvidenciaConsulta(id=evidencia_id, consulta_id=consulta.id, tipo="INFORME_INTERNO",
                clave=borrador.informe_clave, huella=borrador.informe_huella, tamano_bytes=borrador.informe_tamano,
                tipo_contenido="application/pdf", version_generador=version_informe(borrador.resultado)))
            sesion.flush()
            consulta.estado = resultado.estado_ejecucion.value
            consulta.conclusion = resultado.conclusion_busqueda.value
            consulta.resultado = resultado.model_dump(mode="json")
            consulta.finalizada_en = self.reloj()
            trabajo.fase = "FINALIZADA"
            trabajo.concesion_hasta = None
            self._evento(sesion, consulta.id, "FINALIZADA", ActorListas(consulta.actor_emisor, consulta.actor_sujeto, frozenset()),
                         {"estado": consulta.estado, "numero_control": concesion.numero_control})
            return evidencia_id

    def _guardar_resultados(self, sesion, consulta, resultado):
        fijadas = {c.id: c for c in sesion.execute(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta.id)).scalars()}
        if consulta.implementacion == "archivos":
            versiones = {v.id: v for v in sesion.execute(select(VersionFuente).where(VersionFuente.id.in_([c.version_id for c in fijadas.values()]))
                         .order_by(VersionFuente.id).with_for_update(read=True)).scalars()}
            if set(fijadas) != {c.id for c in resultado.cobertura}:
                raise ConflictoListas("La cobertura no corresponde a la fijada")
            for cobertura in resultado.cobertura:
                fijada = fijadas[cobertura.id]
                if (cobertura.version_id != fijada.version_id or cobertura.revision_activa != fijada.revision_activa
                        or cobertura.hash_contenido != fijada.detalle["huella_contenido"]
                        or cobertura.fuente_codigo != fijada.detalle["fuente_codigo"]):
                    raise ConflictoListas("No se cambian versiones fijadas al admitir")
                if cobertura.estado == "CONSULTADA" and versiones[fijada.version_id].estado != "VALIDA":
                    raise VersionNoDisponible("Versión bloqueada durante la consulta; cierre concluyente rechazado")
                fijada.estado = cobertura.estado
        else:
            for cobertura in resultado.cobertura:
                sesion.add(ConsultaFuente(id=cobertura.id, consulta_id=consulta.id, nombre_origen=cobertura.nombre_origen,
                    estado=cobertura.estado, requerida=cobertura.requerida, version_externa=cobertura.version_declarada,
                    detalle=cobertura.model_dump(mode="json")))
        sesion.flush()
        for candidato in resultado.candidatos:
            sesion.add(CoincidenciaLista(id=candidato.id, consulta_id=consulta.id, consulta_fuente_id=candidato.cobertura_id,
                registro_id=candidato.registro_id, version_id=fijadas[candidato.cobertura_id].version_id if fijadas else None,
                identificador_externo=candidato.uid_origen, datos_candidato=candidato.model_dump(mode="json")))
        for hallazgo in resultado.hallazgos_no_estructurados:
            sesion.add(HallazgoProveedor(id=hallazgo.id, consulta_id=consulta.id, contenido=hallazgo.model_dump(mode="json")))

    def fallar(self, concesion: ConcesionConsulta, codigo: str, indeterminada: bool = False):
        with self.sesiones.begin() as sesion:
            trabajo = self._exigir_concesion(sesion, concesion)
            consulta = sesion.get(ConsultaLista, concesion.consulta_id)
            consulta.estado = "INDETERMINADA" if indeterminada else "FALLIDA"
            consulta.conclusion = "NO_CONCLUYENTE"
            consulta.finalizada_en = self.reloj()
            trabajo.error = codigo
            trabajo.fase = "FINALIZADA"
            trabajo.concesion_hasta = None
            self._evento(sesion, consulta.id, "FALLO_TECNICO", ActorListas(consulta.actor_emisor, consulta.actor_sujeto, frozenset()), {"codigo": codigo})

    def leer_informe(self, actor: ActorListas, consulta_id: UUID) -> bytes:
        actor.exigir("listas.ver_evidencias")
        if not self.puede_acceder_consulta(actor, consulta_id):
            raise PermissionError("Sin acceso al historial de la consulta")
        with self.sesiones() as sesion:
            evidencia = sesion.execute(select(EvidenciaConsulta).where(EvidenciaConsulta.consulta_id == consulta_id,
                                       EvidenciaConsulta.tipo == "INFORME_INTERNO")).scalar_one()
            try:
                contenido = self.custodia.leer(evidencia.clave, evidencia.huella, evidencia.tamano_bytes)
            except ErrorIntegridadEvidencia:
                with self.sesiones.begin() as registro:
                    self._evento(registro, consulta_id, "EVIDENCIA_NO_INTEGRA", actor, {"evidencia_id": str(evidencia.id)})
                raise
        with self.sesiones.begin() as sesion:
            self._evento(sesion, consulta_id, "EVIDENCIA_LEIDA", actor, {"tipo": "INFORME_INTERNO"})
        return contenido

    def obtener_consulta(self, actor: ActorListas, consulta_id: UUID) -> dict:
        actor.exigir("listas.ver_evidencias")
        if not self.puede_acceder_consulta(actor, consulta_id):
            raise PermissionError("Sin acceso al historial de la consulta")
        with self.sesiones() as sesion:
            consulta = sesion.get(ConsultaLista, consulta_id)
            if consulta is None:
                raise ConflictoListas("Consulta inexistente")
            fuentes = list(sesion.execute(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta_id)).scalars())
            evidencias = list(sesion.execute(select(EvidenciaConsulta).where(EvidenciaConsulta.consulta_id == consulta_id)).scalars())
            revisiones = list(sesion.execute(select(RevisionCumplimiento).where(RevisionCumplimiento.consulta_id == consulta_id)
                                             .order_by(RevisionCumplimiento.creado_en, RevisionCumplimiento.id)).scalars())
            return {"consulta_id": str(consulta.id), "estado": consulta.estado, "conclusion": consulta.conclusion,
                    "criterio_original": consulta.criterio_original, "manifiesto": consulta.manifiesto,
                    "implementacion": consulta.implementacion, "proveedor": consulta.proveedor,
                    "resultado": consulta.resultado,
                    "fuentes": [{"id": str(f.id), "version_id": str(f.version_id) if f.version_id else None,
                                 "nombre_origen": f.nombre_origen, "detalle": f.detalle} for f in fuentes],
                    "evidencias": [{"id": str(e.id), "tipo": e.tipo, "huella": e.huella} for e in evidencias],
                    "revisiones": [{"id": str(r.id), "resultado": r.resultado, "justificacion": r.justificacion,
                                    "revision_previa_id": str(r.revision_previa_id) if r.revision_previa_id else None} for r in revisiones]}

    def listar_historial_expediente(self, actor: ActorListas, expediente_id: str, limite: int = 50) -> list[dict]:
        actor.exigir("listas.ver_evidencias")
        if not self.puede_acceder_expediente(actor, expediente_id):
            raise PermissionError("Sin acceso al expediente")
        if not 1 <= limite <= 100:
            raise ValueError("Límite fuera de rango")
        with self.sesiones() as sesion:
            consultas = sesion.execute(select(ConsultaLista).where(ConsultaLista.expediente_id == expediente_id)
                         .order_by(ConsultaLista.creado_en.desc(), ConsultaLista.id.desc()).limit(limite)).scalars()
            return [{"consulta_id": str(c.id), "estado": c.estado, "conclusion": c.conclusion,
                     "creado_en": c.creado_en.isoformat(), "sujeto_rol": c.sujeto_rol} for c in consultas]

    def revisar(self, actor: ActorListas, consulta_id: UUID, resultado: str, justificacion: str,
                coincidencia_id: UUID | None = None, revision_previa_id: UUID | None = None) -> UUID:
        actor.exigir("listas.revisar")
        if not self.puede_acceder_consulta(actor, consulta_id):
            raise PermissionError("Sin acceso a la consulta")
        if not justificacion.strip():
            raise ValueError("Se requiere justificación")
        identificador = uuid4()
        with self.sesiones.begin() as sesion:
            consulta = sesion.get(ConsultaLista, consulta_id)
            if consulta is None or consulta.estado in {"PENDIENTE", "EN_CURSO"}:
                raise ConflictoListas("La consulta todavía no tiene resultado final")
            sesion.add(RevisionCumplimiento(id=identificador, consulta_id=consulta_id, coincidencia_id=coincidencia_id,
                revision_previa_id=revision_previa_id, resultado=resultado, justificacion=justificacion,
                actor_emisor=actor.issuer, actor_sujeto=actor.sub))
        return identificador

    @staticmethod
    def _validar_resultado(datos):
        modelo = ResultadoBusquedaF6 if datos.get("version_contrato") == "2.1" else ResultadoProveedorV2
        return modelo.model_validate(datos)

    @staticmethod
    def _validar_resultado_fijado(sesion, consulta, resultado):
        if consulta.version_contrato != "2.1":
            return
        from services.listas.admision_archivos import leer_manifiesto
        busqueda, _, _ = leer_manifiesto(consulta.manifiesto)
        if consulta.manifiesto["criterio_efectivo"] != consulta.criterio_original:
            raise ErrorIntegridadEvidencia("El criterio admitido no coincide con el manifiesto")
        fijadas = {c.id: c for c in sesion.scalars(select(ConsultaFuente).where(ConsultaFuente.consulta_id == consulta.id))}
        if set(fijadas) != {c.id for c in resultado.cobertura}:
            raise ConflictoListas("Cobertura distinta de la admitida")
        for cobertura in resultado.cobertura:
            fijada = fijadas[cobertura.id]
            if (cobertura.fuente_codigo, cobertura.version_id, cobertura.revision_activa, cobertura.hash_contenido) != (
                fijada.detalle["fuente_codigo"], fijada.version_id, fijada.revision_activa, fijada.detalle["huella_contenido"]):
                raise ConflictoListas("El resultado no conserva las versiones admitidas")
        if any((c.regla_version, c.algoritmo_version) != (busqueda.reglas_version, busqueda.algoritmo_version)
               for c in resultado.candidatos):
            raise ConflictoListas("No se sustituyen las reglas admitidas")

    @staticmethod
    def _trabajo_bloqueado(sesion, consulta_id):
        return sesion.execute(select(TrabajoConsulta).where(TrabajoConsulta.consulta_id == consulta_id).with_for_update()).scalar_one()

    def _exigir_concesion(self, sesion, concesion):
        trabajo = self._trabajo_bloqueado(sesion, concesion.consulta_id)
        if (trabajo.numero_control != concesion.numero_control or trabajo.concesion_hasta is None
                or trabajo.concesion_hasta <= self.reloj() or trabajo.fase == "FINALIZADA"):
            raise TrabajoNoVigente("Concesión vencida o sustituida por otro ejecutor")
        return trabajo

    @staticmethod
    def _evento(sesion, consulta_id, tipo, actor, detalle):
        sesion.add(EventoConsulta(consulta_id=consulta_id, tipo=tipo, detalle=detalle,
                                  actor_emisor=actor.issuer, actor_sujeto=actor.sub))
