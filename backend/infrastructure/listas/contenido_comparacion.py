"""Representación de comparación; las referencias completas permanecen en el historial."""
from services.listas.informes import calcular_huella


def contenido_canonico(contenido, por_referencia=False):
    # El orden de alias/documentos no cambia su significado; se conservan duplicados.
    if por_referencia:
        return {'uid': contenido['uid'], 'clase': contenido['clase'],
                'huellas_secciones': {k: calcular_huella(v) for k, v in contenido.items() if k not in ('uid','clase')}}
    return {'uid': contenido['uid'], 'clase': contenido['clase'],
            'campos': sorted(contenido['campos'], key=calcular_huella)}

