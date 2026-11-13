"""Administración local: solicitud inmutable, aprobación explícita y ejecución auditada."""
from infrastructure.listas.adaptadores_archivos import fuentes_habilitadas
from contextlib import contextmanager
from uuid import UUID, uuid4
from sqlalchemy import select, text
from domain.listas.errores import ConflictoListas, ErrorIntegridadEvidencia
from services.listas.autorizacion_administrativa import exigir_entorno_sintetico, exigir_revision, exigir_ejecucion
from services.listas.politica_v2 import ActorListas
from services.listas.informes import calcular_huella
from services.listas.integridad_administrativa import verificar_version
from infrastructure.persistencia.modelos_listas import (
    FuenteLista, FuenteVersionActiva, VersionFuente, ComparacionVersion, PoliticaListas,
    RecepcionFuente, RevisionComparacion, EventoActivacion, EventoVersion, ArchivoFuente, RegistroLista)
from infrastructure.persistencia.modelos_administracion_listas import (
    SolicitudAdministrativaLista, TrabajoComparacionLista, OperacionAdministrativaLista, EventoAdministrativoLista)


class ServicioAdministracionVersiones:
    def __init__(self, sesiones, custodia, politica, actor, entorno, politica_vigente,
                 validar_identidad=None, observador=None):
        exigir_entorno_sintetico(entorno)
        self.sesiones, self.custodia, self.politica, self.actor = sesiones, custodia, politica, actor
        self.politica_vigente = politica_vigente
        self.validar_identidad = validar_identidad or (lambda: None)
        self.observador = observador or (lambda *_: None)
        self.correlacion_id = str(uuid4())

    def _autorizar(self, operacion):
        self.politica.administracion(self.actor, operacion)

    def _fuente(self, sesion, identificador):
        fuente = sesion.get(FuenteLista, identificador)
        if fuente is None or fuente.codigo not in fuentes_habilitadas():
            raise LookupError('Fuente administrativa no disponible')
        return fuente

    def _objeto(self, sesion, tabla, identificador):
        objeto = sesion.get(tabla, identificador)
        if objeto is None:
            raise LookupError('Recurso administrativo no disponible')
        self._fuente(sesion, objeto.fuente_id)
        return objeto

    def _evento(self, sesion, fuente, tipo, detalle):
        sesion.add(EventoAdministrativoLista(fuente_id=fuente, actor_emisor=self.actor.issuer,
            actor_sujeto=self.actor.sub, tipo=tipo, detalle={'correlacion_id': self.correlacion_id, **detalle}))

    @contextmanager
    def _operacion(self, fuente, tipo, datos):
        huella = calcular_huella(datos.model_dump(mode='json'))
        with self.sesiones.begin() as sesion:
            self._fuente(sesion, fuente)
            # Serializa la misma identidad/operación/clave, incluso entre fuentes.
            llave = calcular_huella([self.actor.issuer, self.actor.sub, tipo, datos.clave])
            sesion.execute(text('SELECT pg_advisory_xact_lock(:clave)'), {'clave': int(llave[:15], 16)})
            sesion.scalar(select(FuenteVersionActiva).where(FuenteVersionActiva.fuente_id == fuente).with_for_update())
            previo = sesion.scalar(select(OperacionAdministrativaLista).where(
                OperacionAdministrativaLista.actor_emisor == self.actor.issuer,
                OperacionAdministrativaLista.actor_sujeto == self.actor.sub,
                OperacionAdministrativaLista.operacion == tipo,
                OperacionAdministrativaLista.clave == datos.clave))
            if previo and (previo.huella != huella or previo.fuente_id != fuente):
                raise ConflictoListas('Clave utilizada con otro contenido')
            resultado = dict(previo.resultado) if previo else {}
            yield sesion, resultado, previo is not None
            self.validar_identidad()
            if not previo:
                sesion.add(OperacionAdministrativaLista(fuente_id=fuente, actor_emisor=self.actor.issuer,
                    actor_sujeto=self.actor.sub, operacion=tipo, clave=datos.clave, huella=huella, resultado=resultado))
                self._evento(sesion, fuente, tipo, {'resultado': resultado, 'huella_peticion': huella})
                self.observador('antes_commit', tipo)
        self.observador('despues_commit', tipo)

    def _origen(self, tabla, identificador):
        with self.sesiones() as sesion:
            return self._objeto(sesion, tabla, identificador).fuente_id

    def comparar(self, datos):
        self._autorizar('comparar')
        with self._operacion(datos.fuente_id, 'COMPARACION_SOLICITADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                destino = self._objeto(sesion, VersionFuente, datos.destino_id)
                puntero = sesion.get(FuenteVersionActiva, datos.fuente_id)
                if destino.fuente_id != datos.fuente_id or destino.estado != 'VALIDA' or puntero.revision != datos.revision_esperada or puntero.version_id == destino.id:
                    raise ConflictoListas('Destino o revisión de comparación no disponible')
                identificador = uuid4()
                sesion.add(TrabajoComparacionLista(id=identificador, fuente_id=datos.fuente_id,
                    base_id=puntero.version_id, destino_id=destino.id, revision_base=puntero.revision,
                    actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub))
                resultado.update(comparacion_id=str(identificador), estado='PENDIENTE')
        return resultado

    def informe(self, identificador, pagina=0, limite=50):
        self._autorizar('ver')
        if pagina < 0 or not 1 <= limite <= 100:
            raise ValueError('Paginación inválida')
        with self.sesiones() as sesion:
            trabajo = self._objeto(sesion, TrabajoComparacionLista, identificador)
            salida = {'comparacion_id': str(trabajo.id), 'estado': trabajo.estado, 'error': trabajo.error,
                      'base_id': str(trabajo.base_id) if trabajo.base_id else None,
                      'destino_id': str(trabajo.destino_id), 'revision_base': trabajo.revision_base}
            if trabajo.estado == 'COMPLETADO':
                comparacion = sesion.get(ComparacionVersion, identificador)
                if comparacion.huella != calcular_huella(comparacion.informe):
                    raise ErrorIntegridadEvidencia('Informe de comparación alterado')
                informe = dict(comparacion.informe)
                cambios = informe.pop('cambios')
                salida.update(informe=informe, huella=comparacion.huella, total_cambios=len(cambios),
                              cambios=cambios[pagina*limite:(pagina+1)*limite], pagina=pagina)
            return salida

    def _politica(self, sesion, identificador):
        if identificador != self.politica_vigente():
            raise ConflictoListas('La política administrativa cambió')
        politica = sesion.get(PoliticaListas, identificador)
        if (politica is None or not (politica.parametros.get('solo_pruebas') is True or politica.parametros.get('uso_local') is True)
                or politica.huella != calcular_huella(politica.parametros)
                or not politica.aprobador_emisor.strip() or not politica.aprobador_sujeto.strip()):
            raise ConflictoListas('Política local no aprobada o incompatible')
        return politica

    def _comparacion_vigente(self, sesion, comparacion):
        puntero = sesion.get(FuenteVersionActiva, comparacion.fuente_id)
        if (puntero.version_id, puntero.revision) != (comparacion.base_id, comparacion.revision_base):
            raise ConflictoListas('La selección activa cambió; compare y revise nuevamente')
        if comparacion.huella != calcular_huella(comparacion.informe):
            raise ErrorIntegridadEvidencia('Informe alterado')
        return puntero

    def solicitar(self, datos):
        self._autorizar('comparar')
        fuente = self._origen(ComparacionVersion, datos.comparacion_id)
        with self._operacion(fuente, 'SOLICITUD_CREADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                comparacion = sesion.get(ComparacionVersion, datos.comparacion_id)
                if sesion.get(TrabajoComparacionLista, comparacion.id) is None:
                    raise ConflictoListas('Se requiere una comparación del circuito nuevo')
                self._comparacion_vigente(sesion, comparacion)
                self._politica(sesion, datos.politica_id)
                if datos.tipo == 'REVERSION' and not sesion.scalar(select(EventoActivacion.id).where(
                        EventoActivacion.fuente_id == fuente, EventoActivacion.destino_id == comparacion.destino_id).limit(1)):
                    raise ConflictoListas('Solo se restaura una versión que estuvo activa')
                identificador = uuid4()
                sesion.add(SolicitudAdministrativaLista(id=identificador, fuente_id=fuente,
                    comparacion_id=comparacion.id, politica_id=datos.politica_id, tipo=datos.tipo,
                    actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub, motivo=datos.motivo))
                resultado.update(solicitud_id=str(identificador), estado='PENDIENTE')
        return resultado

    def _contexto(self, sesion, identificador):
        solicitud = self._objeto(sesion, SolicitudAdministrativaLista, identificador)
        comparacion = sesion.get(ComparacionVersion, solicitud.comparacion_id)
        # Mismo orden en todas las mutaciones: fuente, versiones, comparación, solicitud.
        ids = sorted({v for v in (comparacion.base_id, comparacion.destino_id) if v})
        versiones = {v.id: v for v in sesion.scalars(select(VersionFuente).where(VersionFuente.id.in_(ids)).order_by(VersionFuente.id).with_for_update())}
        sesion.scalar(select(ComparacionVersion).where(ComparacionVersion.id == comparacion.id).with_for_update())
        sesion.scalar(select(SolicitudAdministrativaLista).where(SolicitudAdministrativaLista.id == solicitud.id).with_for_update())
        destino = versiones[comparacion.destino_id]
        recepcion = sesion.get(RecepcionFuente, destino.recepcion_id)
        solicitante = ActorListas(solicitud.actor_emisor, solicitud.actor_sujeto, frozenset())
        cargador = ActorListas(recepcion.actor_emisor, recepcion.actor_sujeto, frozenset())
        return solicitud, comparacion, destino, solicitante, cargador

    def decidir(self, datos):
        self._autorizar('aprobar')
        fuente = self._origen(SolicitudAdministrativaLista, datos.solicitud_id)
        with self._operacion(fuente, 'DECISION_REGISTRADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                solicitud, comparacion, destino, solicitante, cargador = self._contexto(sesion, datos.solicitud_id)
                exigir_revision(self.actor, solicitante, cargador, solicitud.tipo)
                if sesion.scalar(select(RevisionComparacion.id).where(RevisionComparacion.solicitud_id == solicitud.id)):
                    raise ConflictoListas('La solicitud ya tiene decisión; cree otra para reconsiderar')
                self._comparacion_vigente(sesion, comparacion)
                self._politica(sesion, solicitud.politica_id)
                if destino.estado != 'VALIDA':
                    raise ConflictoListas('Destino no válido')
                identificador = uuid4()
                sesion.add(RevisionComparacion(id=identificador, solicitud_id=solicitud.id,
                    comparacion_id=comparacion.id, decision=datos.decision,
                    actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub, motivo=datos.motivo))
                resultado.update(revision_id=str(identificador), estado=datos.decision)
        return resultado

    def ejecutar(self, datos):
        self._autorizar('activar')
        self._autorizar('aprobar')
        fuente = self._origen(SolicitudAdministrativaLista, datos.solicitud_id)
        # Custodia fuera de bloqueos; metadatos de versiones selladas son inmutables.
        with self.sesiones() as sesion:
            solicitud = sesion.get(SolicitudAdministrativaLista, datos.solicitud_id)
            comparacion = sesion.get(ComparacionVersion, solicitud.comparacion_id)
            previo = sesion.scalar(select(EventoActivacion).where(EventoActivacion.solicitud_id == solicitud.id))
            if previo is None:
                verificar_version(sesion, self.custodia, sesion.get(VersionFuente, comparacion.destino_id))
        with self._operacion(fuente, 'OPERACION_EJECUTADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                solicitud, comparacion, destino, solicitante, cargador = self._contexto(sesion, datos.solicitud_id)
                aprobacion = sesion.get(RevisionComparacion, datos.aprobacion_id)
                if aprobacion is None or aprobacion.solicitud_id != solicitud.id or aprobacion.decision != 'APROBADA':
                    raise ConflictoListas('Aprobación no corresponde a la solicitud')
                exigir_ejecucion(self.actor, ActorListas(aprobacion.actor_emisor, aprobacion.actor_sujeto, frozenset()),
                                  solicitante, cargador, solicitud.tipo)
                if sesion.scalar(select(EventoActivacion.id).where(EventoActivacion.solicitud_id == solicitud.id)):
                    raise ConflictoListas('Solicitud ya ejecutada; recupere su evento')
                if sesion.scalar(select(RevisionComparacion.id).where(RevisionComparacion.revoca_revision_id == aprobacion.id)):
                    raise ConflictoListas('Aprobación revocada')
                puntero = self._comparacion_vigente(sesion, comparacion)
                if puntero.revision != datos.revision_esperada or destino.estado != 'VALIDA':
                    raise ConflictoListas('Revisión o destino no disponible')
                self._politica(sesion, solicitud.politica_id)
                identificador = uuid4()
                sesion.add(EventoActivacion(id=identificador, solicitud_id=solicitud.id, fuente_id=fuente,
                    anterior_id=puntero.version_id, destino_id=destino.id, comparacion_id=comparacion.id,
                    aprobacion_id=aprobacion.id, revision_anterior=puntero.revision, revision_nueva=puntero.revision+1,
                    tipo=solicitud.tipo, actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub,
                    motivo=solicitud.motivo, politica_id=solicitud.politica_id,
                    clave_idempotencia=datos.clave, huella_peticion=calcular_huella(datos.model_dump(mode='json'))))
                puntero.version_id = destino.id
                puntero.revision += 1
                resultado.update(evento_id=str(identificador), version_id=str(destino.id), revision=puntero.revision)
        return resultado

    def revocar(self, datos):
        self._autorizar('aprobar')
        with self.sesiones() as sesion:
            revision = sesion.get(RevisionComparacion, datos.objeto_id)
            if revision is None or revision.solicitud_id is None:
                raise LookupError('Aprobación no disponible')
            solicitud_id = revision.solicitud_id
        fuente = self._origen(SolicitudAdministrativaLista, solicitud_id)
        with self._operacion(fuente, 'APROBACION_REVOCADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                solicitud, comparacion, *_ = self._contexto(sesion, solicitud_id)
                aprobacion = sesion.get(RevisionComparacion, datos.objeto_id)
                if aprobacion.decision != 'APROBADA' or sesion.scalar(select(RevisionComparacion.id).where(RevisionComparacion.revoca_revision_id == aprobacion.id)):
                    raise ConflictoListas('Aprobación no revocable')
                if sesion.scalar(select(EventoActivacion.id).where(EventoActivacion.solicitud_id == solicitud.id)):
                    raise ConflictoListas('Operación ejecutada; restaurar exige otra solicitud')
                identificador = uuid4()
                sesion.add(RevisionComparacion(id=identificador, solicitud_id=solicitud.id, comparacion_id=comparacion.id,
                    decision='REVOCADA', revoca_revision_id=aprobacion.id, actor_emisor=self.actor.issuer,
                    actor_sujeto=self.actor.sub, motivo=datos.motivo))
                resultado.update(revision_id=str(identificador), estado='REVOCADA')
        return resultado

    def bloquear(self, datos):
        self._autorizar('bloquear')
        fuente = self._origen(VersionFuente, datos.objeto_id)
        with self._operacion(fuente, 'VERSION_BLOQUEADA', datos) as (sesion, resultado, repetida):
            if not repetida:
                version = sesion.scalar(select(VersionFuente).where(VersionFuente.id == datos.objeto_id).with_for_update())
                if version.estado != 'BLOQUEADA':
                    anterior = version.estado
                    version.estado = 'BLOQUEADA'
                    sesion.add(EventoVersion(version_id=version.id, estado_anterior=anterior, estado_nuevo='BLOQUEADA',
                        actor_emisor=self.actor.issuer, actor_sujeto=self.actor.sub, motivo=datos.motivo))
                resultado.update(version_id=str(version.id), estado='BLOQUEADA')
        return resultado

    def consultar_solicitud(self, identificador):
        self._autorizar('ver')
        with self.sesiones() as sesion:
            solicitud = self._objeto(sesion, SolicitudAdministrativaLista, identificador)
            revisiones = list(sesion.scalars(select(RevisionComparacion).where(RevisionComparacion.solicitud_id == identificador).order_by(RevisionComparacion.creado_en)))
            evento = sesion.scalar(select(EventoActivacion).where(EventoActivacion.solicitud_id == identificador))
            estado = 'EJECUTADA' if evento else ('REVOCADA' if any(r.decision == 'REVOCADA' for r in revisiones) else revisiones[0].decision if revisiones else 'PENDIENTE')
            return {'solicitud_id': str(identificador), 'estado': estado, 'tipo': solicitud.tipo, 'motivo': solicitud.motivo,
                    'comparacion_id': str(solicitud.comparacion_id), 'politica_id': str(solicitud.politica_id),
                    'solicitante': {'emisor': solicitud.actor_emisor, 'sujeto': solicitud.actor_sujeto},
                    'revisiones': [{'id': str(r.id), 'decision': r.decision, 'motivo': r.motivo,
                                   'emisor': r.actor_emisor, 'sujeto': r.actor_sujeto} for r in revisiones],
                    'evento_id': str(evento.id) if evento else None}

    def evidencia(self, version_id, tipo):
        self._autorizar('ver')
        from infrastructure.listas.recepcion_archivo import original_verificado
        from infrastructure.persistencia.modelos_listas import EsquemaFuente
        copia = None
        try:
            with self.sesiones.begin() as sesion:
                version = self._objeto(sesion, VersionFuente, version_id)
                opciones = {'original': version.archivo_raiz_id, 'contenido': version.archivo_contenido_id,
                            'esquema': sesion.get(EsquemaFuente, version.esquema_id).archivo_id,
                            'validacion': UUID(version.manifiesto['informe_validacion_id'])}
                if tipo not in opciones:
                    raise ValueError('Tipo de evidencia desconocido')
                archivo = sesion.get(ArchivoFuente, opciones[tipo])
                copia = original_verificado(self.custodia, archivo.huella, archivo.tamano_bytes)
                self.validar_identidad()
                self._evento(sesion, version.fuente_id, 'DESCARGA_AUTORIZADA',
                             {'version_id': str(version.id), 'tipo': tipo, 'huella': archivo.huella})
            return copia
        except BaseException:
            if copia is not None:
                copia.close()
            raise


    def fuentes(self):
        self._autorizar('ver')
        with self.sesiones() as sesion:
            return [{'fuente_id': str(f.id), 'codigo': f.codigo, 'nombre': f.nombre} for f in sesion.scalars(
                select(FuenteLista).where(FuenteLista.codigo.in_(fuentes_habilitadas())))]

    def versiones(self, fuente_id, pagina=0, limite=50):
        self._autorizar('ver')
        if pagina < 0 or not 1 <= limite <= 100:
            raise ValueError('Paginación inválida')
        with self.sesiones() as sesion:
            self._fuente(sesion, fuente_id)
            puntero = sesion.get(FuenteVersionActiva, fuente_id)
            versiones = sesion.scalars(select(VersionFuente).where(VersionFuente.fuente_id == fuente_id)
                .order_by(VersionFuente.creado_en, VersionFuente.id).offset(pagina*limite).limit(limite))
            return {'fuente_id': str(fuente_id), 'revision': puntero.revision,
                    'activa_id': str(puntero.version_id) if puntero.version_id else None,
                    'versiones': [{'version_id': str(v.id), 'estado': v.estado, 'recepcion_id': str(v.recepcion_id),
                                   'registros': v.cantidad_registros, 'manifiesto': v.manifiesto} for v in versiones]}


    def registro_conservado(self, version_id, registro_id):
        """Detalle de una referencia del informe administrativo; no realiza búsquedas."""
        self._autorizar('ver')
        with self.sesiones.begin() as sesion:
            version = self._objeto(sesion, VersionFuente, version_id)
            verificar_version(sesion, self.custodia, version, permitir_bloqueada=True)
            registro = sesion.get(RegistroLista, registro_id)
            if registro is None or registro.version_id != version.id:
                raise LookupError('Registro no disponible en esa versión')
            if calcular_huella(registro.contenido_original) != registro.huella_semantica:
                raise ErrorIntegridadEvidencia('Registro conservado alterado')
            self._evento(sesion, version.fuente_id, 'REGISTRO_CONSULTADO',
                {'version_id': str(version.id), 'registro_id': str(registro.id)})
            return {'version_id': str(version.id), 'registro_id': str(registro.id),
                    'uid': registro.uid_original, 'huella': registro.huella_semantica,
                    'contenido': registro.contenido_original}
