"""Verificación de versiones selladas antes de su uso administrativo."""
from infrastructure.listas.adaptadores_archivos import obtener_adaptador, exigir_adaptador_habilitado
import json
from uuid import UUID
from infrastructure.persistencia.modelos_listas import ArchivoFuente, EsquemaFuente
from infrastructure.listas.recepcion_archivo import original_verificado
from services.listas.informes import calcular_huella
from domain.listas.errores import ErrorIntegridadEvidencia, ConflictoListas


def verificar_version(sesion, custodia, version, permitir_bloqueada=False):
    estados = {'VALIDA', 'BLOQUEADA'} if permitir_bloqueada else {'VALIDA'}
    adaptador = obtener_adaptador(version.formato)
    exigir_adaptador_habilitado(adaptador)
    if version.estado not in estados:
        raise ConflictoListas('La versión no está disponible para administración local')
    manifiesto = dict(version.manifiesto)
    huella = manifiesto.pop('huella_manifiesto', None)
    if huella != calcular_huella(manifiesto):
        raise ErrorIntegridadEvidencia('Manifiesto alterado')
    esquema = sesion.get(EsquemaFuente, version.esquema_id)
    if esquema is None or not esquema.aprobado or esquema.fuente_id != version.fuente_id:
        raise ErrorIntegridadEvidencia('Esquema no aprobado')
    try:
        informe_id = UUID(manifiesto['informe_validacion_id'])
        objetos = (
            (version.archivo_raiz_id, manifiesto['original_sha256'], manifiesto['original_tamano']),
            (version.archivo_contenido_id, manifiesto['contenido_sha256'], manifiesto['contenido_tamano']),
            (esquema.archivo_id, manifiesto['esquema_sha256'], manifiesto['esquema_tamano']),
        )
        for identificador, huella_objeto, tamano in objetos:
            archivo = sesion.get(ArchivoFuente, identificador)
            if archivo is None or (archivo.huella, archivo.tamano_bytes) != (huella_objeto, tamano):
                raise ErrorIntegridadEvidencia('Metadatos de evidencia incompatibles')
            with original_verificado(custodia, archivo.huella, archivo.tamano_bytes):
                pass
        informe = sesion.get(ArchivoFuente, informe_id)
        if informe is None:
            raise ErrorIntegridadEvidencia('Falta informe de validación')
        with original_verificado(custodia, informe.huella, informe.tamano_bytes) as copia:
            datos = json.load(copia)
        if datos.get('resultado') != 'VALIDO' or datos.get('contenido_sha256') != version.huella_contenido or datos.get('esquema_sha256') != manifiesto['esquema_sha256']:
            raise ErrorIntegridadEvidencia('Informe incompatible con versión')
    except (KeyError, ValueError, OSError) as error:
        raise ErrorIntegridadEvidencia('Paquete de evidencias incompleto') from error
    return huella
