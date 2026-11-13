"""Un trabajo administrativo por ejecución; una caída revierte el informe completo."""
from infrastructure.listas.adaptadores_archivos import fuentes_habilitadas, obtener_adaptador
from datetime import datetime, timezone
from sqlalchemy import select, text, func
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico
from services.listas.integridad_administrativa import verificar_version
from services.listas.comparacion_versiones import comparar_registros, VERSION_COMPARADOR
from services.listas.informes import calcular_huella
from infrastructure.persistencia.modelos_listas import VersionFuente, ComparacionVersion, RegistroLista, FuenteLista, IntentoImportacion
from infrastructure.persistencia.modelos_administracion_listas import TrabajoComparacionLista, EventoAdministrativoLista


class TrabajadorComparacionListas:
    def __init__(self, sesiones, custodia, entorno, habilitado=False, observador=None):
        exigir_entorno_sintetico(entorno)
        if not habilitado:
            raise PermissionError('Administración deshabilitada')
        self.sesiones, self.custodia = sesiones, custodia
        self.observador = observador or (lambda *_: None)

    def ejecutar_uno(self):
        trabajo_id = None
        with self.sesiones.begin() as sesion:
            # Comparte el cupo con recepción validada/importación; la caída libera el bloqueo.
            if not sesion.scalar(text('SELECT pg_try_advisory_xact_lock(523003)')):
                return False
            if sesion.scalar(select(IntentoImportacion.id).where(
                    IntentoImportacion.estado == 'EN_CURSO',
                    IntentoImportacion.concesion_hasta > datetime.now(timezone.utc)).limit(1)):
                return False
            # Perfil local explícito: no pretende acreditar capacidad OFAC.
            sesion.execute(text("SET LOCAL statement_timeout = '30s'"))
            trabajo = sesion.scalar(select(TrabajoComparacionLista).where(TrabajoComparacionLista.estado == 'PENDIENTE')
                .order_by(TrabajoComparacionLista.creado_en).with_for_update(skip_locked=True).limit(1))
            if trabajo is None:
                return False
            try:
                fuente = sesion.get(FuenteLista, trabajo.fuente_id)
                if fuente.codigo not in fuentes_habilitadas():
                    raise ConflictoListas('Fuente no habilitada para administración local')
                base = sesion.get(VersionFuente, trabajo.base_id) if trabajo.base_id else None
                destino = sesion.get(VersionFuente, trabajo.destino_id)
                for version in (base, destino):
                    if version:
                        if version.cantidad_registros > obtener_adaptador(version.formato).perfil.comparacion_registros or sesion.scalar(select(func.count()).select_from(RegistroLista).where(RegistroLista.version_id == version.id)) != version.cantidad_registros:
                            raise ConflictoListas('Conteo incompatible con perfil local')
                        verificar_version(sesion, self.custodia, version, permitir_bloqueada=version is base)
                informe = comparar_registros(sesion, base, destino)
                informe['revision_base'] = trabajo.revision_base
                sesion.add(ComparacionVersion(id=trabajo.id, fuente_id=trabajo.fuente_id, base_id=trabajo.base_id,
                    destino_id=trabajo.destino_id, revision_base=trabajo.revision_base,
                    version_comparador=VERSION_COMPARADOR, informe=informe, huella=calcular_huella(informe)))
                sesion.flush()
                trabajo.estado = 'COMPLETADO'
            except (ConflictoListas, ErrorIntegridadEvidencia):
                trabajo.estado, trabajo.error = 'FALLIDO', 'COMPARACION_NO_DISPONIBLE'
            sesion.add(EventoAdministrativoLista(fuente_id=trabajo.fuente_id,
                actor_emisor='servicio-local', actor_sujeto='comparador-listas-v2', tipo='COMPARACION_FINALIZADA',
                detalle={'comparacion_id': str(trabajo.id), 'estado': trabajo.estado, 'error': trabajo.error}))
            # Se captura antes del commit: tras cerrar la sesión el objeto ya no puede leerse.
            trabajo_id = str(trabajo.id)
            self.observador('antes_commit', trabajo_id)
        self.observador('despues_commit', trabajo_id)
        return True
