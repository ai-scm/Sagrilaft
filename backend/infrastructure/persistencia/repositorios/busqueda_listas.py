"""Generación atómica y lectura fijada. No admite peticiones HTTP ni clasifica."""
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select

from domain.listas.contratos_busqueda import VersionBusquedaFijada
from domain.listas.datos_busqueda import ReferenciaDato, RegistroBusqueda, RelacionFuente
from domain.listas.errores import ErrorIntegridadEvidencia, VersionNoDisponible
from infrastructure.listas.adaptadores_busqueda import obtener_lector
from infrastructure.listas.representacion_busqueda import NORMALIZACION_BUSQUEDA, terminos_de
from infrastructure.persistencia.modelos_busqueda_listas import GeneracionBusqueda, RegistroBusquedaPersistido, TerminoBusqueda
from infrastructure.persistencia.modelos_listas import FuenteLista, FuenteVersionActiva, RegistroLista, RelacionRegistro, VersionFuente
from services.listas.informes import calcular_huella
from services.listas.integridad_administrativa import verificar_version


@dataclass(frozen=True)
class DatoNoInterpretado:
    registro_id: UUID
    campos: tuple[str, ...]


@dataclass(frozen=True)
class RegistroExcluido:
    registro_id: UUID
    motivo: str


@dataclass(frozen=True)
class LecturaGeneracion:
    registros: tuple[RegistroBusqueda, ...]
    no_interpretados: tuple[DatoNoInterpretado, ...]
    excluidos: tuple[RegistroExcluido, ...]


def sobre_registro(registro, exclusion=None, pendientes=()):
    return {"registro": registro.model_dump(mode="json") if registro else None,
            "motivo_exclusion": exclusion, "campos_no_interpretados": list(pendientes)}


def iniciar_huella_generacion(generacion):
    resumen = sha256()
    receta = {"version": str(generacion.version_id), "adaptador": generacion.adaptador_version,
              "normalizacion": generacion.normalizacion_version, "catalogo": generacion.catalogo_huella}
    resumen.update(calcular_huella(receta).encode())
    return resumen


def huella_generacion(generacion, filas):
    resumen = iniciar_huella_generacion(generacion)
    for fila in filas:
        resumen.update(str(fila.registro_id).encode())
        resumen.update(fila.huella.encode())
    return resumen.hexdigest()


class RepositorioBusquedaListas:
    def __init__(self, sesiones, custodia, politica, catalogo):
        self.sesiones = sesiones
        self.custodia = custodia
        self.politica = politica
        self.catalogo = catalogo

    def preparar(self, actor, version_id, observador=None):
        """Una transacción por generación; una interrupción obliga a repetirla completa."""
        self.politica.administracion(actor, "comparar")
        with self.sesiones.begin() as sesion:
            # Serializa dos preparaciones de la misma versión, también con recetas distintas.
            version = sesion.scalar(select(VersionFuente).where(VersionFuente.id == version_id).with_for_update().execution_options(populate_existing=True))
            if version is None or version.estado != "VALIDA":
                raise VersionNoDisponible("Se requiere una versión validada y sellada")
            verificar_version(sesion, self.custodia, version)
            lector = obtener_lector(version.formato)
            generacion = sesion.scalar(select(GeneracionBusqueda).where(
                GeneracionBusqueda.version_id == version.id,
                GeneracionBusqueda.adaptador_version == lector.VERSION_ADAPTADOR,
                GeneracionBusqueda.normalizacion_version == NORMALIZACION_BUSQUEDA,
                GeneracionBusqueda.catalogo_huella == self.catalogo.huella))
            if generacion is not None:
                self._verificar(sesion, generacion, conservar=False)
                return generacion.id
            generacion = GeneracionBusqueda(id=uuid4(), version_id=version.id,
                adaptador_version=lector.VERSION_ADAPTADOR, normalizacion_version=NORMALIZACION_BUSQUEDA,
                catalogo_huella=self.catalogo.huella, cantidad_registros=version.cantidad_registros,
                cantidad_consultables=0, huella="0" * 64)
            sesion.add(generacion)
            sesion.flush()
            fuente = sesion.get(FuenteLista, version.fuente_id)
            originales = sesion.scalars(select(RegistroLista).where(RegistroLista.version_id == version.id)
                .order_by(RegistroLista.id).execution_options(yield_per=128))
            resumen = iniciar_huella_generacion(generacion)
            cantidad = 0
            consultables = 0
            for original in originales:
                if calcular_huella(original.contenido_original) != original.huella_semantica:
                    raise ErrorIntegridadEvidencia("Registro original alterado")
                referencia = ReferenciaDato(fuente_codigo=fuente.codigo, version_id=version.id,
                    registro_id=original.id, campo_original="registro_lista/contenido_original")
                if original.tipo_sujeto not in {"PERSONA", "ENTIDAD"}:
                    registro, pendientes, exclusion = None, (), "TIPO_FUERA_DEL_ALCANCE"
                else:
                    registro, pendientes = lector.interpretar(original.contenido_original, referencia, self.catalogo)
                    registro = self._relaciones(sesion, original, registro, fuente.codigo)
                    exclusion = None
                    consultables += 1
                sobre = sobre_registro(registro, exclusion, pendientes)
                fila = RegistroBusquedaPersistido(generacion_id=generacion.id, version_id=version.id,
                    registro_id=original.id, datos=sobre if registro else None,
                    motivo_exclusion=exclusion, huella=calcular_huella(sobre))
                sesion.add(fila)
                sesion.flush()
                if registro:
                    for clase, ordinal, huella in terminos_de(registro):
                        sesion.add(TerminoBusqueda(generacion_id=generacion.id, registro_id=original.id,
                            clase=clase, ordinal=ordinal, huella_valor=huella))
                sesion.flush()
                resumen.update(str(fila.registro_id).encode())
                resumen.update(fila.huella.encode())
                cantidad += 1
                sesion.expunge(fila)
                if observador:
                    observador("registro_preparado", original.id)
            if cantidad != version.cantidad_registros:
                raise ErrorIntegridadEvidencia("Cantidad original incompatible con el sellado")
            generacion.huella = resumen.hexdigest()
            generacion.cantidad_consultables = consultables
            generacion.estado = "LISTA"
            sesion.flush()
            self._verificar(sesion, generacion, conservar=False)
            if observador:
                observador("antes_confirmar", generacion.id)
            return generacion.id

    @staticmethod
    def _relaciones(sesion, original, registro, fuente_codigo):
        relaciones = []
        filas = sesion.scalars(select(RelacionRegistro).where(
            RelacionRegistro.version_id == original.version_id,
            RelacionRegistro.registro_origen_id == original.id).order_by(RelacionRegistro.id))
        for fila in filas:
            if fila.registro_destino_id is None:
                raise ErrorIntegridadEvidencia("Relación importada sin destino resuelto")
            relaciones.append(RelacionFuente(tipo=fila.tipo, direccion="SALIENTE", fuente_destino=fuente_codigo,
                version_destino_id=original.version_id, registro_destino_id=fila.registro_destino_id,
                referencia=registro.referencia.model_copy(update={"campo_original": "relacion_registro/" + str(fila.id)})))
        return RegistroBusqueda.model_validate({**registro.model_dump(), "relaciones": relaciones})

    @staticmethod
    def _verificar(sesion, generacion, conservar=True):
        if generacion.estado != "LISTA":
            raise VersionNoDisponible("Representación de búsqueda no terminada")
        consulta = select(RegistroBusquedaPersistido).where(
            RegistroBusquedaPersistido.generacion_id == generacion.id).order_by(
            RegistroBusquedaPersistido.registro_id).execution_options(populate_existing=True, yield_per=128)
        resumen = iniciar_huella_generacion(generacion)
        filas = []
        cantidad = consultables = 0
        for lote in sesion.scalars(consulta).partitions(128):
            terminos = defaultdict(set)
            for registro_id, clase, ordinal, huella in sesion.execute(select(
                    TerminoBusqueda.registro_id, TerminoBusqueda.clase,
                    TerminoBusqueda.ordinal, TerminoBusqueda.huella_valor).where(
                    TerminoBusqueda.generacion_id == generacion.id,
                    TerminoBusqueda.registro_id.in_([fila.registro_id for fila in lote]))):
                terminos[registro_id].add((clase, ordinal, huella))
            for fila in lote:
                resumen.update(str(fila.registro_id).encode())
                resumen.update(fila.huella.encode())
                cantidad += 1
                sobre = fila.datos if fila.datos is not None else sobre_registro(None, fila.motivo_exclusion)
                if calcular_huella(sobre) != fila.huella:
                    raise ErrorIntegridadEvidencia("Datos derivados alterados")
                esperados = set()
                if fila.datos:
                    registro = RegistroBusqueda.model_validate(fila.datos["registro"])
                    if (registro.referencia.version_id, registro.referencia.registro_id) != (fila.version_id, fila.registro_id):
                        raise ErrorIntegridadEvidencia("Registro derivado de otra versión")
                    esperados = set(terminos_de(registro))
                    consultables += 1
                if esperados != terminos[fila.registro_id]:
                    raise ErrorIntegridadEvidencia("Índice derivado incompleto o alterado")
                if conservar:
                    filas.append(fila)
        if cantidad != generacion.cantidad_registros or resumen.hexdigest() != generacion.huella:
            raise ErrorIntegridadEvidencia("Generación de búsqueda incompleta o alterada")
        if consultables != generacion.cantidad_consultables:
            raise ErrorIntegridadEvidencia("Conteo consultable incompatible")
        return filas

    def fijar_activas(self, sesion, generaciones_por_fuente):
        """Usar dentro de la transacción de admisión autorizada; no hace commit propio.

        El servidor elige las generaciones explícitamente, nunca el navegador.
        Un error debe abortar la admisión o convertirse en cobertura no disponible.
        """
        if not generaciones_por_fuente:
            raise ValueError("Se requiere al menos una fuente")
        fijadas = []
        for codigo, generacion_id in sorted(generaciones_por_fuente.items()):
            fuente = sesion.scalar(select(FuenteLista).where(FuenteLista.codigo == codigo))
            if fuente is None:
                raise VersionNoDisponible("Fuente no registrada")
            activa = sesion.scalar(select(FuenteVersionActiva).where(
                FuenteVersionActiva.fuente_id == fuente.id).with_for_update(read=True).execution_options(populate_existing=True))
            if activa is None or activa.version_id is None:
                raise VersionNoDisponible("Fuente sin versión activa")
            version = sesion.scalar(select(VersionFuente).where(VersionFuente.id == activa.version_id).with_for_update(read=True).execution_options(populate_existing=True))
            generacion = sesion.get(GeneracionBusqueda, generacion_id, populate_existing=True)
            if generacion is None or generacion.version_id != version.id or version.estado != "VALIDA":
                raise VersionNoDisponible("La generación no corresponde a la versión activa válida")
            lector = obtener_lector(version.formato)
            if (generacion.adaptador_version, generacion.normalizacion_version, generacion.catalogo_huella) != (
                    lector.VERSION_ADAPTADOR, NORMALIZACION_BUSQUEDA, self.catalogo.huella):
                raise VersionNoDisponible("La generación requiere otra receta de preparación")
            self._comprobar_sellado(version)
            self._verificar(sesion, generacion, conservar=False)
            if not generacion.cantidad_consultables:
                raise VersionNoDisponible("La fuente no contiene sujetos dentro del alcance")
            fijadas.append(VersionBusquedaFijada(fuente_codigo=codigo, version_id=version.id,
                revision_activa=activa.revision, hash_contenido=version.huella_contenido,
                generacion_id=generacion.id, generacion_hash=generacion.huella,
                version_adaptador=generacion.adaptador_version, version_normalizacion=generacion.normalizacion_version))
        return tuple(fijadas)

    @staticmethod
    def _comprobar_sellado(version):
        manifiesto = dict(version.manifiesto or {})
        huella = manifiesto.pop("huella_manifiesto", None)
        if huella != calcular_huella(manifiesto) or manifiesto.get("contenido_sha256") != version.huella_contenido:
            raise ErrorIntegridadEvidencia("Sellado original incompatible")

    def leer_fijada(self, sesion, fijada):
        """No requiere que siga activa, pero un bloqueo impide continuar esa búsqueda."""
        version = sesion.scalar(select(VersionFuente).where(VersionFuente.id == fijada.version_id).with_for_update(read=True).execution_options(populate_existing=True))
        generacion = sesion.get(GeneracionBusqueda, fijada.generacion_id, populate_existing=True)
        if version is None or version.estado != "VALIDA" or generacion is None:
            raise VersionNoDisponible("Versión fijada indisponible; no se sustituye")
        fuente = sesion.get(FuenteLista, version.fuente_id)
        if (fuente.codigo, version.huella_contenido, generacion.version_id, generacion.huella,
            generacion.adaptador_version, generacion.normalizacion_version) != (
            fijada.fuente_codigo, fijada.hash_contenido, fijada.version_id, fijada.generacion_hash,
            fijada.version_adaptador, fijada.version_normalizacion):
            raise ErrorIntegridadEvidencia("Manifiesto fijado incompatible")
        self._comprobar_sellado(version)
        filas = self._verificar(sesion, generacion)
        return LecturaGeneracion(
            registros=tuple(RegistroBusqueda.model_validate(f.datos["registro"]) for f in filas if f.datos),
            no_interpretados=tuple(DatoNoInterpretado(f.registro_id, tuple(f.datos["campos_no_interpretados"]))
                for f in filas if f.datos and f.datos["campos_no_interpretados"]),
            excluidos=tuple(RegistroExcluido(f.registro_id, f.motivo_exclusion) for f in filas if not f.datos))
