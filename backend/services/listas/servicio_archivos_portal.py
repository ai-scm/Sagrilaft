"""Criterios de los dos circuitos del expediente; sin presentación ni decisiones."""
from sqlalchemy import select, text

from domain.listas.catalogos_busqueda import PAISES_ISO_3166_1_ALPHA_2
from domain.listas.contratos_busqueda import CrearConsultaBusqueda, SolicitudIdempotenteBusqueda
from domain.listas.errores import ConflictoListas
from infrastructure.listas.configuracion_archivos import ConfiguracionArchivosLocal
from infrastructure.persistencia.models import Formulario
from infrastructure.persistencia.modelos_listas import ConsultaLista
from infrastructure.persistencia.modelos_grupos_listas import GrupoConsultaLista
from services.listas.admision_archivos import AdmisionArchivos, sellar_manifiesto
from services.listas.informes import calcular_huella
from services.listas.motor_busqueda import CATALOGO_MOTOR
from services.listas.preparacion_criterios import DatosExpedienteBusqueda, preparar_expediente


def datos_guardados(expediente):
    datos = {campo: getattr(expediente, campo, None) for campo in DatosExpedienteBusqueda.model_fields if campo != "expediente_id"}
    return DatosExpedienteBusqueda(expediente_id=expediente.id, **datos)


def recuperar_reintento(servicio, peticion):
    contexto = peticion.solicitud.contexto
    ambito = f"expediente:{contexto.expediente_id}:{contexto.sujeto_rol}"
    with servicio.sesiones() as sesion:
        anterior = sesion.scalar(select(ConsultaLista).where(ConsultaLista.actor_emisor == servicio.actor.issuer,
            ConsultaLista.actor_sujeto == servicio.actor.sub, ConsultaLista.ambito_idempotencia == ambito,
            ConsultaLista.clave_idempotencia == peticion.clave))
        if anterior:
            if anterior.huella_peticion != peticion.hash_cuerpo:
                raise ConflictoListas("La clave corresponde a otros criterios de consulta")
            return anterior.id


def admisor(servicio):
    configuracion = ConfiguracionArchivosLocal.cargar(servicio.entorno)
    return AdmisionArchivos(servicio.sesiones, servicio.custodia, servicio.politica, configuracion)


def admitir(servicio, peticion, criterio, preparacion=None, sesion=None, grupo_id=None):
    componente = admisor(servicio)
    inicial = sellar_manifiesto(dict(implementacion="archivos", solicitud_original=peticion.solicitud.model_dump(mode="json"),
        criterio_efectivo=criterio.model_dump(mode="json"), preparacion=preparacion,
        fuentes_solicitadas=list(componente.configuracion.fuentes), politica_solicitada=str(componente.configuracion.politica_id)))
    return servicio.repositorio.admitir(servicio.actor, peticion, "archivos_locales", inicial,
        politica_id=componente.configuracion.politica_id, sesion_actual=sesion, grupo_id=grupo_id,
        criterio_efectivo=criterio,
        preparar_admision=lambda transaccion, identificador: componente.preparar(transaccion,
            identificador, peticion.solicitud, criterio, preparacion))


def crear_individual(servicio, solicitud, clave):
    peticion = SolicitudIdempotenteBusqueda(clave=clave, solicitud=solicitud)
    anterior = recuperar_reintento(servicio, peticion)
    if anterior:
        return anterior
    if servicio.politica.config.implementacion != "archivos":
        from domain.listas.puertos import ListasNoDisponibles
        raise ListasNoDisponibles("El contrato 2.1 requiere selección explícita de archivos")
    with servicio.sesiones.begin() as sesion:
        expediente = sesion.scalar(select(Formulario).where(Formulario.id == solicitud.contexto.expediente_id)
            .with_for_update(read=True).execution_options(populate_existing=True))
        naturaleza = (expediente.tipo_persona or "").casefold()
        representante = solicitud.contexto.sujeto_rol == "REPRESENTANTE"
        if representante and naturaleza not in {"juridica", "jurídica"}:
            raise ValueError("El expediente no tiene un representante separado consultable")
        tipo = "PERSONA" if representante or naturaleza == "natural" else "ENTIDAD" if naturaleza in {"juridica", "jurídica"} else "NO_DETERMINADO"
        if solicitud.criterio.tipo_sujeto not in {"NO_DETERMINADO", tipo}:
            raise ValueError("La naturaleza consultada no corresponde al sujeto del expediente")
        criterio = solicitud.criterio.model_copy(update={"tipo_sujeto": tipo})
        # El servidor nunca agrega por su cuenta nacimiento, documento o país guardados a un
        # nombre editado por el usuario: si el criterio los trae (p. ej. precargados por el
        # portal y confirmados por quien consulta), es porque la persona que consulta los
        # declaró explícitamente, no porque el sistema los haya inferido.
        # El país del documento sí se acepta si la persona que consulta lo declara explícitamente
        # (nunca se asume): sin él, ningún documento puede confirmar jurisdicción ni llegar a ALTA.
        for identificador in criterio.identificadores:
            if identificador.pais_emisor and identificador.pais_emisor not in PAISES_ISO_3166_1_ALPHA_2:
                raise ValueError("El país del documento no es un código ISO 3166-1 válido")
        return admitir(servicio, peticion, criterio, sesion=sesion)


def crear_grupo(servicio, expediente_id, clave, sesion, grupo_id):
    expediente = sesion.scalar(select(Formulario).where(Formulario.id == expediente_id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    preparacion = preparar_expediente(datos_guardados(expediente), CATALOGO_MOTOR)
    respuesta = dict(grupo_id=str(grupo_id), consultas=[], no_consultados=[
        dict(sujeto_rol=s.rol, motivo=s.motivo) for s in preparacion.omitidos])
    sesion.execute(text("SET CONSTRAINTS fk_consulta_grupo DEFERRED"))
    for sujeto in preparacion.sujetos:
        solicitud = CrearConsultaBusqueda(contexto=dict(tipo="EXPEDIENTE", expediente_id=expediente_id, sujeto_rol=sujeto.rol),
            criterio=sujeto.criterio)
        peticion = SolicitudIdempotenteBusqueda(clave=f"grupo:{grupo_id}:{sujeto.rol}", solicitud=solicitud)
        identificador = admitir(servicio, peticion, sujeto.criterio, sujeto.model_dump(mode="json"), sesion, grupo_id)
        respuesta["consultas"].append(dict(consulta_id=str(identificador), sujeto_rol=sujeto.rol))
    sesion.add(GrupoConsultaLista(id=grupo_id, actor_emisor=servicio.actor.issuer, actor_sujeto=servicio.actor.sub,
        expediente_id=expediente_id, clave=clave,
        huella=calcular_huella({"expediente": expediente_id, "operacion": "ambos_sujetos_v1"}), respuesta=respuesta))
    return respuesta
