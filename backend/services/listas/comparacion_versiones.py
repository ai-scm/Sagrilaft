"""Comparación exacta de registros versionados; no decide riesgo ni sanciones."""
import json
from sqlalchemy import select
from infrastructure.persistencia.modelos_listas import RegistroLista
from services.listas.informes import calcular_huella
from domain.listas.errores import ConflictoListas

VERSION_COMPARADOR = 'campos-y-referencias-v2'


from infrastructure.listas.contenido_comparacion import contenido_canonico

def comparar_registros(sesion, base, destino):
    if base and (base.formato, base.version_normalizador, base.version_importador) != (
            destino.formato, destino.version_normalizador, destino.version_importador):
        raise ConflictoListas('Versiones de formato o software incompatibles')
    from infrastructure.listas.adaptadores_archivos import obtener_adaptador
    adaptador = obtener_adaptador(destino.formato)
    limite = adaptador.perfil.comparacion_bytes
    referencias = {}
    consumidos = 0
    def contenidos(version):
        nonlocal consumidos
        salida = {}
        if version is None:
            return salida
        consulta = select(RegistroLista).where(RegistroLista.version_id == version.id).order_by(RegistroLista.uid_original)
        for registro in sesion.scalars(consulta.execution_options(yield_per=100)):
            contenido = contenido_canonico(registro.contenido_original, adaptador.comparacion_por_referencia)
            consumidos += len(json.dumps(contenido, ensure_ascii=False).encode('utf-8'))
            if consumidos > limite:
                raise ConflictoListas('Comparación excede el límite del perfil local')
            salida[registro.uid_original] = contenido
            referencias[(str(version.id), registro.uid_original)] = str(registro.id)
        return salida
    anteriores, nuevos = contenidos(base), contenidos(destino)
    cambios = []
    iguales = 0
    for identificador in sorted(anteriores.keys() | nuevos.keys()):
        antes, despues = anteriores.get(identificador), nuevos.get(identificador)
        if antes == despues:
            iguales += 1
            continue
        tipo = 'ALTA' if antes is None else 'BAJA' if despues is None else 'MODIFICACION'
        if adaptador.comparacion_por_referencia:
            antes = ({**antes, 'version_id': str(base.id), 'registro_id': referencias[(str(base.id), identificador)]} if antes else None)
            despues = ({**despues, 'version_id': str(destino.id), 'registro_id': referencias[(str(destino.id), identificador)]} if despues else None)
        cambios.append({'uid': identificador, 'tipo': tipo, 'antes': antes, 'despues': despues})
    return {'comparador': VERSION_COMPARADOR, 'base_id': str(base.id) if base else None,
            'destino_id': str(destino.id), 'base_manifiesto': base.manifiesto['huella_manifiesto'] if base else None,
            'destino_manifiesto': destino.manifiesto['huella_manifiesto'],
            'normalizador': destino.version_normalizador, 'importador': destino.version_importador,
            'conteos': {**{tipo: sum(c['tipo'] == tipo for c in cambios) for tipo in ('ALTA','BAJA','MODIFICACION')},
                       'SIN_CAMBIOS': iguales}, 'cambios': cambios}
