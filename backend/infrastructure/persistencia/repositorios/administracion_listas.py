"""Operaciones transaccionales del catálogo; el importador real corresponde a F5."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from domain.listas.errores import ConflictoListas, VersionNoDisponible
from infrastructure.persistencia.modelos_listas import (
    ArchivoFuente, ComparacionVersion, EventoActivacion, EventoVersion, FuenteLista,
    FuenteVersionActiva, PoliticaListas, RecepcionFuente, RevisionComparacion, VersionFuente,
)
from services.listas.informes import calcular_huella
from services.listas.politica_v2 import ActorListas, PoliticaListasV2


@dataclass(frozen=True)
class ActivacionConfirmada:
    evento_id: UUID
    version_id: UUID
    revision: int


class RepositorioAdministracionListas:
    def __init__(self, sesiones, politica: PoliticaListasV2, custodia, verificar_vigencia):
        self.sesiones = sesiones
        self.politica = politica
        self.custodia = custodia
        # Dependencia de política aprobada, nunca un permiso enviado por el navegador.
        self.verificar_vigencia = verificar_vigencia

    def crear_fuente(self, actor: ActorListas, codigo: str, nombre: str, organismo: str, url_oficial: str) -> UUID:
        self.politica.administracion(actor, "cargar")
        identificador = uuid4()
        with self.sesiones.begin() as sesion:
            sesion.add(FuenteLista(id=identificador, codigo=codigo, nombre=nombre, organismo=organismo, url_oficial=url_oficial))
            # El disparador crea el puntero vacío en la misma transacción.
        return identificador

    def revisar(self, actor: ActorListas, comparacion_id: UUID, decision: str, motivo: str) -> UUID:
        if decision not in {"APROBADA", "RECHAZADA"} or not motivo.strip():
            raise ValueError("Decisión o motivo de revisión inválidos")
        self.politica.administracion(actor, "aprobar")
        identificador = uuid4()
        with self.sesiones.begin() as sesion:
            comparacion = sesion.execute(select(ComparacionVersion).where(ComparacionVersion.id == comparacion_id).with_for_update()).scalar_one()
            version = sesion.get(VersionFuente, comparacion.destino_id)
            recepcion = sesion.get(RecepcionFuente, version.recepcion_id)
            cargador = ActorListas(recepcion.actor_emisor, recepcion.actor_sujeto, frozenset())
            self.politica.aprobar(actor, cargador)
            sesion.add(RevisionComparacion(id=identificador, comparacion_id=comparacion_id, decision=decision,
                                           actor_emisor=actor.issuer, actor_sujeto=actor.sub, motivo=motivo))
        return identificador

    def revocar(self, actor: ActorListas, aprobacion_id: UUID, motivo: str) -> UUID:
        self.politica.administracion(actor, "aprobar")
        if not motivo.strip():
            raise ValueError("Se requiere motivo de revocación")
        identificador = uuid4()
        with self.sesiones.begin() as sesion:
            aprobacion = sesion.get(RevisionComparacion, aprobacion_id)
            if aprobacion is None or aprobacion.decision != "APROBADA":
                raise ConflictoListas("Aprobación inexistente")
            sesion.execute(select(ComparacionVersion).where(ComparacionVersion.id == aprobacion.comparacion_id).with_for_update()).scalar_one()
            sesion.add(RevisionComparacion(id=identificador, comparacion_id=aprobacion.comparacion_id,
                                           decision="REVOCADA", revoca_revision_id=aprobacion_id,
                                           actor_emisor=actor.issuer, actor_sujeto=actor.sub, motivo=motivo))
        return identificador

    def activar(self, actor: ActorListas, fuente_id: UUID, comparacion_id: UUID, aprobacion_id: UUID,
                revision_esperada: int, politica_id: UUID, clave_idempotencia: str, motivo: str,
                tipo: str = "ACTIVACION") -> ActivacionConfirmada:
        if tipo not in {"ACTIVACION", "REVERSION"} or not motivo.strip() or not 1 <= len(clave_idempotencia) <= 128:
            raise ValueError("Solicitud de activación inválida")
        self.politica.administracion(actor, "revertir" if tipo == "REVERSION" else "activar")
        huella = calcular_huella(dict(fuente=str(fuente_id), comparacion=str(comparacion_id), aprobacion=str(aprobacion_id),
                                      revision=revision_esperada, politica=str(politica_id), motivo=motivo, tipo=tipo))
        # Comprobar objetos sin sostener bloqueos SQL. No afecta a reintentos confirmados.
        with self.sesiones() as sesion:
            previo = self._evento_previo(sesion, actor, fuente_id, clave_idempotencia, huella)
            if previo:
                return previo
            comparacion = sesion.get(ComparacionVersion, comparacion_id)
            if comparacion is None:
                raise ConflictoListas("Comparación inexistente")
            version = sesion.get(VersionFuente, comparacion.destino_id)
            for identificador in {version.archivo_raiz_id, version.archivo_contenido_id}:
                archivo = sesion.get(ArchivoFuente, identificador)
                self.custodia.leer(archivo.clave, archivo.huella, archivo.tamano_bytes)
        with self.sesiones.begin() as sesion:
            puntero = sesion.execute(select(FuenteVersionActiva).where(FuenteVersionActiva.fuente_id == fuente_id).with_for_update()).scalar_one()
            previo = self._evento_previo(sesion, actor, fuente_id, clave_idempotencia, huella)
            if previo:
                return previo
            if puntero.revision != revision_esperada:
                raise ConflictoListas("La versión activa cambió; compare y revise nuevamente")
            comparacion = sesion.get(ComparacionVersion, comparacion_id)
            identificadores = {comparacion.destino_id}
            if puntero.version_id:
                identificadores.add(puntero.version_id)
            versiones = {v.id: v for v in sesion.execute(select(VersionFuente).where(VersionFuente.id.in_(identificadores)).order_by(VersionFuente.id).with_for_update()).scalars()}
            comparacion = sesion.execute(select(ComparacionVersion).where(ComparacionVersion.id == comparacion_id).with_for_update()).scalar_one()
            if (comparacion.fuente_id != fuente_id or comparacion.base_id != puntero.version_id
                    or comparacion.revision_base != revision_esperada):
                raise ConflictoListas("La comparación no corresponde a la selección actual")
            destino = versiones[comparacion.destino_id]
            if destino.estado != "VALIDA":
                raise VersionNoDisponible("La versión destino no es válida")
            politica = sesion.get(PoliticaListas, politica_id)
            if politica is None:
                raise ConflictoListas("Política no registrada")
            self.verificar_vigencia(sesion, destino, politica)
            aprobacion = sesion.get(RevisionComparacion, aprobacion_id)
            revocada = sesion.execute(select(RevisionComparacion.id).where(RevisionComparacion.revoca_revision_id == aprobacion_id)).first()
            if aprobacion is None or aprobacion.comparacion_id != comparacion_id or aprobacion.decision != "APROBADA" or revocada:
                raise ConflictoListas("La aprobación no está vigente")
            evento_id = uuid4()
            sesion.add(EventoActivacion(id=evento_id, fuente_id=fuente_id, anterior_id=puntero.version_id,
                                       destino_id=destino.id, comparacion_id=comparacion_id, aprobacion_id=aprobacion_id,
                                       revision_anterior=puntero.revision, revision_nueva=puntero.revision + 1,
                                       tipo=tipo, actor_emisor=actor.issuer, actor_sujeto=actor.sub,
                                       motivo=motivo, clave_idempotencia=clave_idempotencia, huella_peticion=huella, politica_id=politica_id))
            puntero.version_id = destino.id
            puntero.revision += 1
            return ActivacionConfirmada(evento_id, destino.id, puntero.revision)

    @staticmethod
    def _evento_previo(sesion, actor, fuente_id, clave, huella):
        evento = sesion.execute(select(EventoActivacion).where(EventoActivacion.actor_emisor == actor.issuer,
            EventoActivacion.actor_sujeto == actor.sub, EventoActivacion.fuente_id == fuente_id,
            EventoActivacion.clave_idempotencia == clave)).scalar_one_or_none()
        if evento:
            if evento.huella_peticion != huella:
                raise ConflictoListas("Clave de idempotencia reutilizada con otro contenido")
            return ActivacionConfirmada(evento.id, evento.destino_id, evento.revision_nueva)
        return None

    def bloquear(self, actor: ActorListas, version_id: UUID, motivo: str) -> None:
        self.politica.administracion(actor, "bloquear")
        if not motivo.strip():
            raise ValueError("Se requiere motivo de bloqueo")
        with self.sesiones.begin() as sesion:
            version = sesion.execute(select(VersionFuente).where(VersionFuente.id == version_id).with_for_update()).scalar_one()
            if version.estado == "BLOQUEADA":
                return
            anterior = version.estado
            version.estado = "BLOQUEADA"
            sesion.add(EventoVersion(version_id=version_id, estado_anterior=anterior, estado_nuevo="BLOQUEADA",
                                     actor_emisor=actor.issuer, actor_sujeto=actor.sub, motivo=motivo))
