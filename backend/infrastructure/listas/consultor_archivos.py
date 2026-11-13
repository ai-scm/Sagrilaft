"""Adaptador 2.1 sobre generaciones fijadas; sin selección ni sustitución de fuentes."""
from datetime import datetime, timezone

from domain.listas.contratos_busqueda import ResultadoBusquedaF6, CapacidadesBusqueda
from domain.listas.errores import ErrorIntegridadEvidencia, VersionNoDisponible
from infrastructure.persistencia.repositorios.busqueda_listas import RepositorioBusquedaListas
from services.listas.admision_archivos import leer_manifiesto
from services.listas.motor_busqueda import MotorBusqueda


class ConsultorArchivos:
    def __init__(self, sesiones, politica, custodia, manifiesto, coberturas):
        self.sesiones = sesiones
        self.fijado, self.catalogo, self.parametros = leer_manifiesto(manifiesto)
        self.preparacion = manifiesto.get("preparacion") or {}
        self.busqueda = RepositorioBusquedaListas(sesiones, custodia, politica, self.catalogo)
        self.coberturas = coberturas

    def capacidades(self):
        return CapacidadesBusqueda(proveedor="archivos_locales", adaptador_version="archivos-f64-v1",
            campos=("nombre", "identificadores", "fecha_nacimiento", "fecha_expedicion", "nacionalidades", "ciudadanias", "ubicaciones"),
            tipos_sujeto=("PERSONA", "ENTIDAD", "NO_DETERMINADO"))

    def consultar(self, solicitud):
        if solicitud.manifiesto != self.fijado or solicitud.implementacion != "archivos":
            raise ErrorIntegridadEvidencia("La solicitud no conserva el manifiesto admitido")
        cobertura, registros, advertencias = [], [], []
        por_fuente = {}
        # Los bloqueos de lectura impiden un bloqueo administrativo a mitad de evaluación.
        with self.sesiones.begin() as sesion:
            for fijada in self.fijado.fuentes:
                datos = self.coberturas[fijada.fuente_codigo]
                base = dict(id=datos["id"], fuente_codigo=fijada.fuente_codigo, nombre_origen=datos["nombre"],
                    version_id=fijada.version_id, revision_activa=fijada.revision_activa, hash_contenido=fijada.hash_contenido,
                    requerida=True)
                try:
                    lectura = self.busqueda.leer_fijada(sesion, fijada)
                except (VersionNoDisponible, ErrorIntegridadEvidencia):
                    cobertura.append({**base, "estado": "FALLIDA", "motivo": "La versión fijada no está disponible o no supera integridad"})
                    advertencias.append(dict(codigo="FUENTE_FIJADA_NO_DISPONIBLE", descripcion="No se sustituyó la fuente fijada", cobertura_id=datos["id"]))
                    continue
                cobertura.append({**base, "estado": "CONSULTADA"})
                registros.extend(lectura.registros)
                por_fuente[fijada.fuente_codigo] = datos["id"]
                if lectura.no_interpretados:
                    advertencias.append(dict(codigo="DATOS_FUENTE_NO_INTERPRETADOS",
                        descripcion=f"{len(lectura.no_interpretados)} registros conservan campos sin interpretar; no se usan como corroboración", cobertura_id=datos["id"]))
            evaluacion = MotorBusqueda(self.catalogo, self.parametros).evaluar(solicitud.criterio, tuple(registros),
                solicitud.consulta_id, por_fuente, solicitud.admitida_en.date()) if por_fuente else None
        completa = bool(evaluacion and evaluacion.concluyente and all(c["estado"] == "CONSULTADA" for c in cobertura))
        no_aplicados = []
        if evaluacion:
            advertencias.extend(dict(codigo=c, descripcion="La evaluación no cubrió todos los criterios o registros requeridos") for c in evaluacion.advertencias)
            no_aplicados.extend(dict(codigo="CRITERIO_NO_APLICADO", descripcion=c) for c in evaluacion.campos_no_aplicados)
            advertencias.append(dict(codigo="ALCANCE_EVALUADO", descripcion=f"Evaluados {evaluacion.registros_evaluados} de {evaluacion.registros_disponibles} registros; recuperados {evaluacion.candidatos_recuperados} candidatos"))
        exigidos_no_interpretados = self.preparacion.get("criterios_exigidos_no_interpretados", ())
        if exigidos_no_interpretados:
            completa = False
            no_aplicados.extend(dict(codigo="CRITERIO_GUARDADO_NO_INTERPRETADO", descripcion=c) for c in exigidos_no_interpretados)
        for aviso in self.preparacion.get("avisos", ()):
            advertencias.append(dict(codigo=aviso["codigo"], descripcion="Dato guardado no interpretado: " + aviso["campo_expediente"]))
        candidatos = evaluacion.candidatos if evaluacion else ()
        estado = "COMPLETADA" if completa else "PARCIAL" if por_fuente else "FALLIDA"
        conclusion = ("CON_CANDIDATOS" if candidatos else "SIN_CANDIDATOS") if completa else "NO_CONCLUYENTE"
        return ResultadoBusquedaF6(consulta_id=solicitud.consulta_id, implementacion="archivos", proveedor="archivos_locales",
            generador_informe_version="informe-listas-f6-v2",
            estado_ejecucion=estado, conclusion_busqueda=conclusion, cobertura=cobertura, candidatos=candidatos,
            advertencias=advertencias, criterios_no_aplicados=no_aplicados, fecha_inicio=solicitud.admitida_en,
            fecha_fin=max(datetime.now(timezone.utc), solicitud.admitida_en))
