"""Entrada privada del subproceso limitado de validación; sin base de datos."""
import json
from pathlib import Path
import resource
import sys


def principal():
    directorio = Path(sys.argv[1])
    solicitud = json.loads((directorio / 'solicitud.json').read_text())
    perfil = solicitud['perfil']
    resource.setrlimit(resource.RLIMIT_AS, (perfil['memoria_bytes'], perfil['memoria_bytes']))
    resource.setrlimit(resource.RLIMIT_CPU, (perfil['validacion_segundos'], perfil['validacion_segundos'] + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (perfil['expandido_bytes'], perfil['expandido_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from infrastructure.listas.validacion_archivo import validar
    try:
        informe = validar(directorio / 'original.bin', directorio, solicitud['formato'], perfil)
    except MemoryError:
        informe = {'resultado': 'INVALIDO', 'codigo': 'LIMITE_MEMORIA'}
    (directorio / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False))


if __name__ == '__main__':
    principal()
