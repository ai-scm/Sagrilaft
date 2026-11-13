"""Trabajador de consultas de listas para ambientes compartidos (servicio ECS).

A diferencia de `trabajador_local`, no exige la base del Docker Compose: usa la
configuración validada de la aplicación y la custodia del entorno (S3 en ECS). Solo
procesa consultas; la administración de listas (recepción, validación, importación)
trabaja sobre disco y sigue limitada al entorno local.

Un error inesperado en una pasada se registra y no detiene el servicio: la consulta
queda con su concesión y se retoma (o queda indeterminada si fue externa y estaba
lanzando) cuando venza. SIGTERM termina la pasada en curso y sale.
"""
import logging
import signal
from threading import Event

ESPERA_SIN_TRABAJO = 2.0
ESPERA_TRAS_ERROR = 10.0


def principal():
    from infrastructure.config.configuracion import load_config
    from infrastructure.listas.custodia import custodia_desde_entorno
    from infrastructure.persistencia import models  # noqa: F401  (registra relaciones antes de crear sesiones)
    from infrastructure.persistencia.database import SessionLocal
    from services.listas.politica_v2 import PoliticaListasV2
    from services.listas.trabajador import TrabajadorListas

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    registro = logging.getLogger("trabajador_listas")
    configuracion = load_config()
    custodia = custodia_desde_entorno()
    if custodia is None:
        raise RuntimeError("El trabajador de listas requiere custodia (LISTAS_CUSTODIA_BACKEND=s3 o LISTAS_CUSTODIA_DIRECTORIO)")
    trabajador = TrabajadorListas(SessionLocal, PoliticaListasV2(configuracion.listas_cautela, configuracion.entorno), custodia)
    detener = Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())
    registro.info("Trabajador de listas iniciado (modalidad %s, entorno %s)",
                  configuracion.listas_cautela.implementacion, configuracion.entorno)
    while not detener.is_set():
        try:
            hubo_trabajo = trabajador.ejecutar_uno()
        except Exception as error:
            # Solo el tipo: los errores de SQLAlchemy traen la fila completa (criterios, nombres).
            registro.error("Falló una pasada del trabajador de listas: %s", type(error).__name__)
            detener.wait(ESPERA_TRAS_ERROR)
            continue
        if not hubo_trabajo:
            detener.wait(ESPERA_SIN_TRABAJO)
    registro.info("Trabajador de listas detenido")


if __name__ == "__main__":
    principal()
