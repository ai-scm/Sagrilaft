"""F5.6: recorrido administrativo completo por CLI/HTTP y procesos locales reales."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
import uvicorn

from api.routers import administracion_versiones
from infrastructure.persistencia.modelos_listas import (
    PoliticaListas, VersionFuente, FuenteVersionActiva, EventoActivacion,
    RevisionComparacion, ArchivoFuente, IntentoImportacion, EventoVersion)
from infrastructure.persistencia.modelos_recepcion_listas import EventoRecepcionLista
from infrastructure.persistencia.modelos_administracion_listas import (
    SolicitudAdministrativaLista, EventoAdministrativoLista, OperacionAdministrativaLista)
from services.listas.informes import calcular_huella
from .test_flujo_http import portal
from .test_recepcion_f52 import carga

RAIZ = Path(__file__).resolve().parents[2]
FIJOS = RAIZ / 'tests/fixtures/listas_f5'
BASE = '/api/administracion-listas'


def cargar_cliente(nombre):
    ruta = RAIZ / 'scripts/listas' / (nombre + '.py')
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize('formato', ['xml', 'zip'])
def test_recorrido_integrado_f56(carga, tmp_path, monkeypatch, capsys, caplog, formato):
    inicio = time.monotonic()
    carga.app.include_router(administracion_versiones.enrutador)
    politica_id = uuid4()
    emisor = carga.app.state.config.keycloak.issuer
    with carga.sesiones.begin() as sesion:
        sesion.add(PoliticaListas(id=politica_id, codigo='ensayo-integrado-f56', version=1,
            parametros={'solo_pruebas': True}, huella=calcular_huella({'solo_pruebas': True}),
            aprobador_emisor=emisor, aprobador_sujeto='revisor-local'))
    monkeypatch.setenv('LISTAS_ADMIN_POLITICA_ID', str(politica_id))
    clientes = {'cargar': cargar_cliente('cargar_sintetico'),
                'administrar': cargar_cliente('administrar_sintetico')}
    identidades = {
        'preparador': carga.token(['listas_cargador'], sub='preparador-local'),
        'revisor': carga.token(['listas_aprobador'], sub='revisor-local'),
    }
    activo = ['preparador']
    # Solo se sustituye la entrada interactiva del JWT, no autenticación ni HTTP.
    monkeypatch.setattr(clientes['cargar'].getpass, 'getpass', lambda _: identidades[activo[0]])
    with socket.socket() as conexion:
        conexion.bind(('127.0.0.1', 0))
        puerto = conexion.getsockname()[1]
    servidor = uvicorn.Server(uvicorn.Config(carga.app, host='127.0.0.1', port=puerto, log_level='error'))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    pasos, tiempos = [], []

    def obtener_http(ruta, identidad=None):
        conexion = http.client.HTTPConnection('127.0.0.1', puerto, timeout=30)
        try:
            conexion.request('GET', BASE + ruta, headers={'Authorization': 'Bearer ' + identidades[identidad or activo[0]]})
            respuesta = conexion.getresponse()
            return respuesta.status, respuesta.read()
        finally:
            conexion.close()

    def consultar(ruta):
        estado, contenido = obtener_http(ruta)
        assert estado == 200, (ruta, estado)
        return json.loads(contenido)

    def cli(operacion, datos=None, identificador=None):
        argumentos = ['administrar_sintetico.py', operacion, '--url', f'http://127.0.0.1:{puerto}']
        if datos is not None:
            archivo = tmp_path / 'peticion.json'
            archivo.write_text(json.dumps(datos))
            argumentos += ['--datos', str(archivo)]
        if identificador:
            argumentos += ['--id', identificador]
        monkeypatch.setattr(sys, 'argv', argumentos)
        clientes['administrar'].principal()
        resultado = json.loads(capsys.readouterr().out)
        pasos.append({'operacion': operacion, 'actor': activo[0], 'resultado': resultado})
        return resultado

    def trabajador(nombre):
        entorno = {**os.environ, 'LISTAS_CUSTODIA_DIRECTORIO': str(carga.custodia.directorio),
                   'LISTAS_ADMIN_HABILITADA': 'true'}
        antes = time.monotonic()
        proceso = subprocess.run([sys.executable, str(RAIZ / 'scripts/validacion' / nombre)],
                                 env=entorno, capture_output=True, text=True, timeout=60)
        assert proceso.returncode == 0, proceso.stderr
        tiempos.append({'proceso': nombre, 'segundos': round(time.monotonic() - antes, 4)})
        pasos.append({'operacion': nombre, 'resultado': proceso.stdout.strip()})

    def recibir(nombre):
        argumentos = ['cargar_sintetico.py', str(FIJOS / nombre), '--url', f'http://127.0.0.1:{puerto}',
                      '--clave', nombre, '--formato', 'SINTETICO_ZIP_V1' if nombre.endswith('.zip') else 'SINTETICO_XML_V1']
        monkeypatch.setattr(sys, 'argv', argumentos)
        clientes['cargar'].principal()
        salida = capsys.readouterr().out
        recepcion = salida.split('Recepción: ', 1)[1].splitlines()[0]
        # El reintento utiliza la misma clave y conserva recepción e intento.
        clientes['cargar'].principal()
        assert 'Original ya recibido' in capsys.readouterr().out
        estado, original = obtener_http(f'/recepciones/{recepcion}/original')
        assert estado == 200 and original == (FIJOS / nombre).read_bytes()
        pasos.append({'operacion': 'recibir_y_reintentar', 'recepcion_id': recepcion,
                      'archivo': nombre, 'sha256': hashlib.sha256(original).hexdigest(), 'bytes': len(original)})
        return recepcion

    def seleccionar(destino, revision, tipo, clave):
        datos = {'fuente_id': fuente, 'destino_id': destino, 'revision_esperada': revision, 'clave': 'comparar-' + clave}
        comparacion = cli('comparar', datos)
        assert cli('comparar', datos) == comparacion
        trabajador('ejecutar_comparacion_listas.py')
        informe = cli('informe', identificador=comparacion['comparacion_id'])
        assert informe['estado'] == 'COMPLETADO'
        solicitud = cli('solicitar', {'comparacion_id': comparacion['comparacion_id'], 'politica_id': str(politica_id),
            'tipo': tipo, 'motivo': 'Ensayo integrado sintético ' + clave, 'clave': 'solicitar-' + clave})
        solicitud_id = solicitud['solicitud_id']
        decision = {'solicitud_id': solicitud_id, 'decision': 'APROBADA',
                    'motivo': 'Informe y original comprobados', 'clave': 'aprobar-' + clave}
        # El preparador no tiene permiso de aprobación ni ejecución.
        with pytest.raises(SystemExit, match='403'):
            cli('decidir', decision, solicitud_id)
        capsys.readouterr()
        activo[0] = 'revisor'
        estado, original = obtener_http(f'/versiones/{destino}/evidencias/original')
        assert estado == 200
        aprobacion = cli('decidir', decision, solicitud_id)
        assert cli('decidir', decision, solicitud_id) == aprobacion
        ejecucion = {'solicitud_id': solicitud_id, 'aprobacion_id': aprobacion['revision_id'],
                     'revision_esperada': revision, 'clave': 'ejecutar-' + clave}
        resultado = cli('ejecutar', ejecucion, solicitud_id)
        assert cli('ejecutar', ejecucion, solicitud_id) == resultado
        assert cli('consultar', identificador=solicitud_id)['estado'] == 'EJECUTADA'
        activo[0] = 'preparador'
        return informe

    try:
        limite = time.monotonic() + 10
        while not servidor.started and time.monotonic() < limite:
            time.sleep(.02)
        assert servidor.started
        fuente = consultar('/fuentes')[0]['fuente_id']
        primera_recepcion = recibir('v1.' + formato)
        trabajador('ejecutar_validacion_archivos.py')
        assert consultar(f'/recepciones/{primera_recepcion}/validacion')['resultado'] == 'VALIDO'
        trabajador('ejecutar_importacion_archivos.py')
        catalogo = consultar(f'/fuentes/{fuente}/versiones')
        assert catalogo['activa_id'] is None and len(catalogo['versiones']) == 1
        primera = catalogo['versiones'][0]
        manifiesto_original = primera['manifiesto']
        version_uno = primera['version_id']
        informe = seleccionar(version_uno, 0, 'ACTIVACION', 'v1')
        assert informe['informe']['conteos']['ALTA'] == 2
        assert consultar(f'/fuentes/{fuente}/versiones')['activa_id'] == version_uno

        segunda_recepcion = recibir('v2.xml')
        trabajador('ejecutar_validacion_archivos.py')
        trabajador('ejecutar_importacion_archivos.py')
        catalogo = consultar(f'/fuentes/{fuente}/versiones')
        version_dos = next(v['version_id'] for v in catalogo['versiones'] if v['version_id'] != version_uno)
        informe = seleccionar(version_dos, 1, 'ACTIVACION', 'v2')
        assert informe['informe']['conteos'] == {'ALTA': 1, 'BAJA': 1, 'MODIFICACION': 1, 'SIN_CAMBIOS': 0}
        assert consultar(f'/fuentes/{fuente}/versiones')['activa_id'] == version_dos

        # Archivo inválido: queda evidencia de validación, no otra versión ni activa cambiada.
        invalida = recibir('invalido.xml')
        trabajador('ejecutar_validacion_archivos.py')
        assert consultar(f'/recepciones/{invalida}/validacion')['resultado'] == 'INVALIDO'
        trabajador('ejecutar_importacion_archivos.py')
        assert consultar(f'/fuentes/{fuente}/versiones')['activa_id'] == version_dos
        seleccionar(version_uno, 2, 'REVERSION', 'restaurar')
        catalogo = consultar(f'/fuentes/{fuente}/versiones')
        assert catalogo['activa_id'] == version_uno and catalogo['revision'] == 3
        assert len(catalogo['versiones']) == 2
        assert next(v for v in catalogo['versiones'] if v['version_id'] == version_uno)['manifiesto'] == manifiesto_original
        estado, original = obtener_http(f'/recepciones/{primera_recepcion}/original')
        assert estado == 200 and original == (FIJOS / ('v1.' + formato)).read_bytes()
        estado, _ = obtener_http(f'/recepciones/{primera_recepcion}/original', identidad='revisor')
        assert estado == 404  # No se reasigna la recepción al revisor.

        with carga.sesiones() as sesion:
            eventos = list(sesion.scalars(select(EventoActivacion).order_by(EventoActivacion.revision_nueva)))
            assert [e.tipo for e in eventos] == ['ACTIVACION', 'ACTIVACION', 'REVERSION']
            assert [e.revision_nueva for e in eventos] == [1, 2, 3]
            assert all(e.actor_sujeto == 'revisor-local' for e in eventos)
            assert sesion.scalar(select(func.count()).select_from(SolicitudAdministrativaLista)) == 3
            assert sesion.scalar(select(func.count()).select_from(RevisionComparacion)) == 3
            assert sesion.scalar(select(func.count()).select_from(IntentoImportacion)) == 3
            assert sesion.get(FuenteVersionActiva, UUID(fuente)).version_id == UUID(version_uno)
            recepciones = list(sesion.scalars(select(EventoRecepcionLista).order_by(EventoRecepcionLista.creado_en)))
            administrativos = list(sesion.scalars(select(EventoAdministrativoLista).order_by(EventoAdministrativoLista.creado_en)))
            tipos = {e.tipo for e in recepciones}
            assert {'RESERVADA', 'RECIBIDA', 'VALIDACION_INICIADA', 'VALIDACION_FINALIZADA',
                    'IMPORTACION_RECLAMADA', 'LOTE_CONFIRMADO', 'IMPORTACION_SELLADA'} <= tipos
            assert {'COMPARACION_SOLICITADA', 'COMPARACION_FINALIZADA', 'SOLICITUD_CREADA',
                    'DECISION_REGISTRADA', 'OPERACION_EJECUTADA', 'DESCARGA_AUTORIZADA'} <= {e.tipo for e in administrativos}
            assert all(e.actor_emisor and e.actor_sujeto and e.creado_en for e in [*recepciones, *administrativos])
            assert sesion.scalar(select(func.count()).select_from(OperacionAdministrativaLista)) == 12
            archivos = list(sesion.scalars(select(ArchivoFuente)))
            for archivo in archivos:
                datos = carga.custodia.leer(archivo.clave, archivo.huella, archivo.tamano_bytes)
                assert hashlib.sha256(datos).hexdigest() == archivo.huella
            auditoria = {
                'recepciones': [{'id': str(e.id), 'recepcion_id': str(e.recepcion_id), 'tipo': e.tipo,
                    'actor': e.actor_sujeto, 'emisor': e.actor_emisor, 'fecha': e.creado_en.isoformat()} for e in recepciones],
                'administracion': [{'id': str(e.id), 'tipo': e.tipo, 'actor': e.actor_sujeto,
                    'emisor': e.actor_emisor, 'fecha': e.creado_en.isoformat(), 'detalle': e.detalle} for e in administrativos],
                'activaciones': [{'id': str(e.id), 'solicitud_id': str(e.solicitud_id), 'aprobacion_id': str(e.aprobacion_id),
                    'anterior_id': str(e.anterior_id) if e.anterior_id else None, 'destino_id': str(e.destino_id),
                    'revision': e.revision_nueva, 'tipo': e.tipo} for e in eventos],
            }
        assert not any(token in caplog.text for token in identidades.values())
        assert 'ADMINISTRACION_DENEGADA_O_FALLIDA' in caplog.text
        evidencia = {'alcance': 'SOLO_SINTETICO_LOCAL', 'formato_inicial': formato, 'fuente_id': fuente,
            'version_final': version_uno, 'revision_final': 3, 'pasos': pasos, 'auditoria': auditoria,
            'integridad': {'archivos_verificados': len(archivos), 'original_final_identico': True,
                          'manifiesto_v1_conservado': True},
            'idempotencia': {'solicitudes': 3, 'decisiones': 3, 'ejecuciones': 3, 'operaciones_unicas': 12},
            'recursos': {'segundos_recorrido': round(time.monotonic()-inicio, 4), 'procesos': tiempos,
                        'max_rss_hijos_acumulado_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                        'bytes_custodia': sum(p.stat().st_size for p in carga.custodia.directorio.iterdir() if p.is_file())}}
        destino = Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO']) / f'recorrido-f56-{formato}.json'
        destino.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2) + '\n')
    finally:
        servidor.should_exit = True
        hilo.join(timeout=10)
        assert not hilo.is_alive()


def test_denegacion_original_deja_auditoria_f56(carga, caplog):
    """El rechazo debe quedar auditable; no basta autenticar al usuario y devolver 404."""
    import logging
    from .test_recepcion_f52 import reservar, enviar
    recepcion = reservar(carga)
    assert enviar(carga, recepcion).status_code == 202
    carga.cliente.headers['Authorization'] = 'Bearer ' + carga.token(['listas_aprobador'], sub='revisor-local')
    caplog.clear()
    with caplog.at_level(logging.INFO):
        respuesta = carga.cliente.get(BASE + f'/recepciones/{recepcion}/original')
    assert respuesta.status_code == 404
    mensajes = [r.getMessage() for r in caplog.records]
    denegaciones = [m for m in mensajes if any(codigo in m for codigo in ('DENEGADA', 'ACCESS_DENIED', 'AUTHZ_DENIED'))]
    with carga.sesiones() as sesion:
        eventos = list(sesion.scalars(select(EventoRecepcionLista).where(EventoRecepcionLista.recepcion_id == UUID(recepcion))))
    eventos_denegados = [e for e in eventos if 'DENEGADA' in e.tipo and e.actor_sujeto == 'revisor-local']
    evidencia = {'caso': 'descarga_por_revisor_sin_propiedad_de_recepcion', 'estado_http': respuesta.status_code,
                'acceso_bloqueado': True, 'denegacion_en_log': bool(denegaciones),
                'denegacion_en_eventos': bool(eventos_denegados),
                'tipos_eventos': [e.tipo for e in eventos],
                'logs': mensajes}
    Path(os.environ['LISTAS_EVIDENCIAS_DIRECTORIO'], 'auditoria-denegacion-f56.json').write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2) + '\n')
    # Se mantiene como regresión normal; no se oculta el resultado con xfail.
    assert denegaciones or eventos_denegados, 'F56-A01: la denegación del original no deja registro explícito de auditoría'


@pytest.mark.parametrize('modo,codigo', [('sin_jwt',401),('jwt_invalido',401),('sin_permiso',403)])
def test_auditoria_rechazos_recepcion_f56(carga,caplog,modo,codigo):
    import logging
    from .test_recepcion_f52 import reservar,enviar
    recepcion=reservar(carga);assert enviar(carga,recepcion).status_code==202
    token='token-no-valido-no-debe-aparecer-en-log'
    if modo=='sin_jwt':
        carga.cliente.headers.pop('Authorization')
    elif modo=='jwt_invalido':
        carga.cliente.headers['Authorization']='Bearer '+token
    else:
        token=carga.token(['listas_operador'],sub='sin-permiso-local')
        carga.cliente.headers['Authorization']='Bearer '+token
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        respuesta=carga.cliente.get(BASE+f'/recepciones/{recepcion}/original')
    assert respuesta.status_code==codigo
    mensajes=[r.getMessage() for r in caplog.records if r.name=='api.routers.recepciones_listas']
    assert len(mensajes)==1
    mensaje=mensajes[0]
    assert 'LISTAS_RECEPCION_DENEGADA' in mensaje and f'codigo={codigo}' in mensaje
    assert 'correlacion=' in mensaje and f'/recepciones/{recepcion}/original' in mensaje
    assert token not in caplog.text
    assert ('actor=sin-permiso-local' if modo=='sin_permiso' else 'actor=IDENTIDAD_NO_VERIFICADA') in mensaje
