"""Catálogo e historial de listas: tablas y protecciones PostgreSQL congeladas.

La revisión no importa modelos de la aplicación: futuras ediciones del ORM no cambian
esta migración. No se permite retroceder si se perderían registros del módulo.
"""
from alembic import op
import sqlalchemy as sa

revision = "a21b34c56d78"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None

TABLAS = ['archivo_fuente', 'fuente_lista', 'politica_listas', 'consulta_lista', 'esquema_fuente', 'recepcion_fuente', 'borrador_consulta', 'evento_consulta', 'evidencia_consulta', 'hallazgo_proveedor', 'trabajo_consulta', 'version_fuente', 'comparacion_version', 'comprobacion_fuente', 'consulta_fuente', 'evento_version', 'fuente_version_activa', 'intento_importacion', 'registro_lista', 'atributo_registro', 'coincidencia_lista', 'direccion_registro', 'identificador_registro', 'nombre_registro', 'relacion_registro', 'revision_comparacion', 'evento_activacion', 'revision_cumplimiento']

SENTENCIAS = (
    """CREATE TABLE archivo_fuente (
	clave VARCHAR(500) NOT NULL,
	nombre_recibido VARCHAR(500) NOT NULL,
	tipo_contenido VARCHAR(100) NOT NULL,
	tamano_bytes BIGINT NOT NULL,
	huella VARCHAR(64) NOT NULL,
	archivo_padre_id UUID,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_archivo_fuente_tamano CHECK (tamano_bytes >= 0),
	CONSTRAINT ck_archivo_fuente_huella CHECK (length(huella) = 64),
	UNIQUE (clave),
	FOREIGN KEY(archivo_padre_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE fuente_lista (
	codigo VARCHAR(64) NOT NULL,
	nombre VARCHAR(200) NOT NULL,
	organismo VARCHAR(200) NOT NULL,
	url_oficial TEXT NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (codigo)
)""",
    """CREATE TABLE politica_listas (
	codigo VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	parametros JSONB NOT NULL,
	huella VARCHAR(64) NOT NULL,
	aprobador_emisor VARCHAR(500) NOT NULL,
	aprobador_sujeto VARCHAR(200) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_politica_listas_version UNIQUE (codigo, version)
)""",
    """CREATE TABLE consulta_lista (
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	expediente_id VARCHAR,
	sujeto_rol VARCHAR(30),
	grupo_id UUID,
	consulta_previa_id UUID,
	motivo TEXT,
	ambito_idempotencia VARCHAR(200) NOT NULL,
	clave_idempotencia VARCHAR(128) NOT NULL,
	huella_peticion VARCHAR(64) NOT NULL,
	implementacion VARCHAR(20) NOT NULL,
	proveedor VARCHAR(64) NOT NULL,
	version_contrato VARCHAR(20) NOT NULL,
	criterio_original JSONB NOT NULL,
	manifiesto JSONB NOT NULL,
	politica_id UUID,
	estado VARCHAR(30) NOT NULL,
	conclusion VARCHAR(30),
	resultado JSONB,
	finalizada_en TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_consulta_peticion UNIQUE (actor_emisor, actor_sujeto, ambito_idempotencia, clave_idempotencia),
	CONSTRAINT ck_consulta_estado CHECK (estado IN ('PENDIENTE','EN_CURSO','COMPLETADA','PARCIAL','FALLIDA','INDETERMINADA')),
	CONSTRAINT ck_consulta_implementacion CHECK (implementacion IN ('simulado','archivos','externo')),
	CONSTRAINT ck_consulta_contexto CHECK ((expediente_id IS NOT NULL AND sujeto_rol IS NOT NULL AND sujeto_rol IN ('CONTRAPARTE','REPRESENTANTE')) OR (expediente_id IS NULL AND sujeto_rol IS NULL AND motivo IS NOT NULL AND length(trim(motivo)) >= 10)),
	CONSTRAINT ck_consulta_cierre CHECK ((estado IN ('PENDIENTE','EN_CURSO') AND conclusion IS NULL AND finalizada_en IS NULL) OR (estado IN ('COMPLETADA','PARCIAL','FALLIDA','INDETERMINADA') AND conclusion IS NOT NULL AND finalizada_en IS NOT NULL)),
	CONSTRAINT ck_consulta_no_concluyente CHECK (estado NOT IN ('PARCIAL','FALLIDA','INDETERMINADA') OR conclusion = 'NO_CONCLUYENTE'),
	CONSTRAINT ck_consulta_conclusion CHECK (conclusion IS NULL OR conclusion IN ('SIN_CANDIDATOS','CON_CANDIDATOS','NO_CONCLUYENTE')),
	CONSTRAINT ck_consulta_fechas CHECK (finalizada_en IS NULL OR finalizada_en >= creado_en),
	FOREIGN KEY(expediente_id) REFERENCES formularios (id) ON DELETE RESTRICT,
	FOREIGN KEY(consulta_previa_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(politica_id) REFERENCES politica_listas (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_consulta_expediente_fecha ON consulta_lista (expediente_id, creado_en)""",
    """CREATE TABLE esquema_fuente (
	fuente_id UUID NOT NULL,
	archivo_id UUID NOT NULL,
	formato VARCHAR(64) NOT NULL,
	version VARCHAR(64) NOT NULL,
	aprobado BOOLEAN NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_esquema_fuente_origen UNIQUE (fuente_id, id),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(archivo_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE recepcion_fuente (
	fuente_id UUID NOT NULL,
	archivo_id UUID,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	url_declarada TEXT NOT NULL,
	descargado_en TIMESTAMP WITH TIME ZONE,
	estado VARCHAR(20) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_recepcion_fuente_origen UNIQUE (fuente_id, id),
	CONSTRAINT ck_recepcion_estado CHECK (estado IN ('PENDIENTE','RECIBIDA','FALLIDA')),
	CONSTRAINT ck_recepcion_archivo CHECK (estado <> 'RECIBIDA' OR archivo_id IS NOT NULL),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(archivo_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE borrador_consulta (
	consulta_id UUID NOT NULL,
	resultado JSONB NOT NULL,
	huella VARCHAR(64) NOT NULL,
	informe_clave VARCHAR(500),
	informe_huella VARCHAR(64),
	informe_tamano BIGINT,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (consulta_id),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE evento_consulta (
	consulta_id UUID NOT NULL,
	tipo VARCHAR(100) NOT NULL,
	detalle JSONB NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE evidencia_consulta (
	consulta_id UUID NOT NULL,
	tipo VARCHAR(30) NOT NULL,
	clave VARCHAR(500) NOT NULL,
	huella VARCHAR(64) NOT NULL,
	tamano_bytes BIGINT NOT NULL,
	tipo_contenido VARCHAR(100) NOT NULL,
	version_generador VARCHAR(64) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_evidencia_objeto UNIQUE (consulta_id, tipo, clave),
	CONSTRAINT ck_evidencia_integridad CHECK (length(huella) = 64 AND tamano_bytes >= 0),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT,
	UNIQUE (clave)
)""",
    """CREATE UNIQUE INDEX uq_evidencia_informe ON evidencia_consulta (consulta_id) WHERE tipo = 'INFORME_INTERNO'""",
    """CREATE TABLE hallazgo_proveedor (
	consulta_id UUID NOT NULL,
	contenido JSONB NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE trabajo_consulta (
	consulta_id UUID NOT NULL,
	fase VARCHAR(30) NOT NULL,
	numero_control BIGINT NOT NULL,
	concesion_hasta TIMESTAMP WITH TIME ZONE,
	ultimo_latido TIMESTAMP WITH TIME ZONE,
	error TEXT,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_trabajo_control CHECK (numero_control >= 0),
	UNIQUE (consulta_id),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_trabajo_concesion ON trabajo_consulta (fase, concesion_hasta)""",
    """CREATE TABLE version_fuente (
	fuente_id UUID NOT NULL,
	recepcion_id UUID NOT NULL,
	esquema_id UUID NOT NULL,
	archivo_raiz_id UUID NOT NULL,
	archivo_contenido_id UUID NOT NULL,
	reconstruye_version_id UUID,
	motivo_reconstruccion TEXT,
	formato VARCHAR(64) NOT NULL,
	version_importador VARCHAR(64) NOT NULL,
	version_normalizador VARCHAR(64) NOT NULL,
	huella_contenido VARCHAR(64) NOT NULL,
	generacion INTEGER NOT NULL,
	estado VARCHAR(30) NOT NULL,
	cantidad_registros INTEGER NOT NULL,
	manifiesto JSONB,
	publicada_en VARCHAR(100),
	origen_fecha VARCHAR(30) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_version_fuente_origen UNIQUE (fuente_id, id),
	CONSTRAINT uq_version_representacion UNIQUE (fuente_id, huella_contenido, formato, esquema_id, version_importador, version_normalizador, generacion),
	CONSTRAINT fk_version_recepcion_origen FOREIGN KEY(fuente_id, recepcion_id) REFERENCES recepcion_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_version_esquema_origen FOREIGN KEY(fuente_id, esquema_id) REFERENCES esquema_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_version_estado CHECK (estado IN ('EN_CONSTRUCCION','VALIDA','BLOQUEADA')),
	CONSTRAINT ck_version_conteos CHECK (generacion >= 0 AND cantidad_registros >= 0),
	CONSTRAINT fk_version_reconstruccion FOREIGN KEY(fuente_id, reconstruye_version_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_version_reconstruccion CHECK ((generacion=0 AND reconstruye_version_id IS NULL) OR (generacion>0 AND reconstruye_version_id IS NOT NULL AND motivo_reconstruccion IS NOT NULL)),
	CONSTRAINT ck_version_sellada CHECK (estado <> 'VALIDA' OR (manifiesto IS NOT NULL AND cantidad_registros > 0)),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(archivo_raiz_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT,
	FOREIGN KEY(archivo_contenido_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT,
	FOREIGN KEY(reconstruye_version_id) REFERENCES version_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_version_fuente_estado ON version_fuente (fuente_id, estado)""",
    """CREATE TABLE comparacion_version (
	fuente_id UUID NOT NULL,
	base_id UUID,
	destino_id UUID NOT NULL,
	revision_base BIGINT NOT NULL,
	version_comparador VARCHAR(64) NOT NULL,
	informe JSONB NOT NULL,
	huella VARCHAR(64) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_comparacion_origen UNIQUE (fuente_id, id),
	CONSTRAINT fk_comparacion_base FOREIGN KEY(fuente_id, base_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_comparacion_destino FOREIGN KEY(fuente_id, destino_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_comparacion_revision CHECK (revision_base >= 0),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE comprobacion_fuente (
	fuente_id UUID NOT NULL,
	version_id UUID,
	archivo_id UUID NOT NULL,
	resultado VARCHAR(30) NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	url_declarada TEXT NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_comprobacion_version FOREIGN KEY(fuente_id, version_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(archivo_id) REFERENCES archivo_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE consulta_fuente (
	consulta_id UUID NOT NULL,
	fuente_id UUID,
	version_id UUID,
	revision_activa BIGINT,
	nombre_origen TEXT NOT NULL,
	version_externa TEXT,
	estado VARCHAR(30) NOT NULL,
	requerida BOOLEAN NOT NULL,
	detalle JSONB NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_cobertura_consulta UNIQUE (consulta_id, id),
	CONSTRAINT uq_cobertura_version UNIQUE (consulta_id, id, version_id),
	CONSTRAINT uq_cobertura_fuente UNIQUE (consulta_id, fuente_id),
	CONSTRAINT fk_cobertura_version FOREIGN KEY(fuente_id, version_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE evento_version (
	version_id UUID NOT NULL,
	estado_anterior VARCHAR(30) NOT NULL,
	estado_nuevo VARCHAR(30) NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	motivo TEXT NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(version_id) REFERENCES version_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE fuente_version_activa (
	fuente_id UUID NOT NULL,
	version_id UUID,
	revision BIGINT NOT NULL,
	PRIMARY KEY (fuente_id),
	CONSTRAINT fk_activa_misma_fuente FOREIGN KEY(fuente_id, version_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_activa_revision CHECK (revision >= 0),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE intento_importacion (
	recepcion_id UUID NOT NULL,
	version_id UUID,
	estado VARCHAR(30) NOT NULL,
	fase VARCHAR(30) NOT NULL,
	numero_control BIGINT NOT NULL,
	concesion_hasta TIMESTAMP WITH TIME ZONE,
	punto_reanudacion JSONB NOT NULL,
	informe JSONB,
	error TEXT,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_importacion_control CHECK (numero_control >= 0),
	FOREIGN KEY(recepcion_id) REFERENCES recepcion_fuente (id) ON DELETE RESTRICT,
	FOREIGN KEY(version_id) REFERENCES version_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE registro_lista (
	version_id UUID NOT NULL,
	uid_original VARCHAR(200) NOT NULL,
	tipo_sujeto VARCHAR(30) NOT NULL,
	contenido_original JSONB NOT NULL,
	huella_semantica VARCHAR(64) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_registro_version_uid UNIQUE (version_id, uid_original),
	CONSTRAINT uq_registro_version_id UNIQUE (version_id, id),
	FOREIGN KEY(version_id) REFERENCES version_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE atributo_registro (
	tipo VARCHAR(100) NOT NULL,
	valor JSONB NOT NULL,
	referencia_original TEXT NOT NULL,
	registro_id UUID NOT NULL,
	ordinal INTEGER NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_atributo_ordinal UNIQUE (registro_id, ordinal),
	FOREIGN KEY(registro_id) REFERENCES registro_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE coincidencia_lista (
	consulta_id UUID NOT NULL,
	consulta_fuente_id UUID NOT NULL,
	version_id UUID,
	registro_id UUID,
	identificador_externo TEXT,
	datos_candidato JSONB NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_coincidencia_consulta UNIQUE (consulta_id, id),
	CONSTRAINT fk_coincidencia_cobertura FOREIGN KEY(consulta_id, consulta_fuente_id) REFERENCES consulta_fuente (consulta_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_coincidencia_version_fijada FOREIGN KEY(consulta_id, consulta_fuente_id, version_id) REFERENCES consulta_fuente (consulta_id, id, version_id) ON DELETE RESTRICT,
	CONSTRAINT fk_coincidencia_registro FOREIGN KEY(version_id, registro_id) REFERENCES registro_lista (version_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_coincidencia_origen CHECK ((version_id IS NULL) = (registro_id IS NULL)),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE direccion_registro (
	original JSONB NOT NULL,
	normalizada JSONB NOT NULL,
	registro_id UUID NOT NULL,
	ordinal INTEGER NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_direccion_ordinal UNIQUE (registro_id, ordinal),
	FOREIGN KEY(registro_id) REFERENCES registro_lista (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE identificador_registro (
	tipo VARCHAR(64) NOT NULL,
	original TEXT NOT NULL,
	normalizado TEXT NOT NULL,
	pais_emisor VARCHAR(10),
	atributos JSONB NOT NULL,
	registro_id UUID NOT NULL,
	ordinal INTEGER NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_identificador_ordinal UNIQUE (registro_id, ordinal),
	FOREIGN KEY(registro_id) REFERENCES registro_lista (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_identificador_busqueda ON identificador_registro (tipo, pais_emisor, normalizado)""",
    """CREATE TABLE nombre_registro (
	original TEXT NOT NULL,
	normalizado TEXT NOT NULL,
	tipo VARCHAR(30) NOT NULL,
	atributos JSONB NOT NULL,
	registro_id UUID NOT NULL,
	ordinal INTEGER NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_nombre_ordinal UNIQUE (registro_id, ordinal),
	FOREIGN KEY(registro_id) REFERENCES registro_lista (id) ON DELETE RESTRICT
)""",
    """CREATE INDEX ix_nombre_normalizado ON nombre_registro (normalizado)""",
    """CREATE TABLE relacion_registro (
	version_id UUID NOT NULL,
	registro_origen_id UUID NOT NULL,
	registro_destino_id UUID,
	identificador_destino TEXT NOT NULL,
	ambito_destino VARCHAR(100) NOT NULL,
	tipo VARCHAR(100) NOT NULL,
	atributos JSONB NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT fk_relacion_origen FOREIGN KEY(version_id, registro_origen_id) REFERENCES registro_lista (version_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_relacion_destino FOREIGN KEY(version_id, registro_destino_id) REFERENCES registro_lista (version_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(version_id) REFERENCES version_fuente (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE revision_comparacion (
	comparacion_id UUID NOT NULL,
	decision VARCHAR(20) NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	motivo TEXT NOT NULL,
	revoca_revision_id UUID,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_revision_comparacion_id UNIQUE (comparacion_id, id),
	CONSTRAINT ck_revision_comparacion_decision CHECK (decision IN ('APROBADA','RECHAZADA','REVOCADA')),
	CONSTRAINT fk_revision_revocada FOREIGN KEY(comparacion_id, revoca_revision_id) REFERENCES revision_comparacion (comparacion_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(comparacion_id) REFERENCES comparacion_version (id) ON DELETE RESTRICT,
	UNIQUE (revoca_revision_id)
)""",
    """CREATE TABLE evento_activacion (
	fuente_id UUID NOT NULL,
	anterior_id UUID,
	destino_id UUID NOT NULL,
	comparacion_id UUID NOT NULL,
	aprobacion_id UUID NOT NULL,
	revision_anterior BIGINT NOT NULL,
	revision_nueva BIGINT NOT NULL,
	tipo VARCHAR(20) NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	motivo TEXT NOT NULL,
	clave_idempotencia VARCHAR(128) NOT NULL,
	huella_peticion VARCHAR(64) NOT NULL,
	politica_id UUID NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_activacion_revision UNIQUE (fuente_id, revision_nueva),
	CONSTRAINT uq_activacion_peticion UNIQUE (actor_emisor, actor_sujeto, fuente_id, clave_idempotencia),
	CONSTRAINT fk_evento_anterior FOREIGN KEY(fuente_id, anterior_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_evento_destino FOREIGN KEY(fuente_id, destino_id) REFERENCES version_fuente (fuente_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_evento_aprobacion FOREIGN KEY(comparacion_id, aprobacion_id) REFERENCES revision_comparacion (comparacion_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_evento_salto_revision CHECK (revision_nueva = revision_anterior + 1),
	CONSTRAINT ck_evento_tipo CHECK (tipo IN ('ACTIVACION','REVERSION')),
	FOREIGN KEY(fuente_id) REFERENCES fuente_lista (id) ON DELETE RESTRICT,
	FOREIGN KEY(politica_id) REFERENCES politica_listas (id) ON DELETE RESTRICT
)""",
    """CREATE TABLE revision_cumplimiento (
	consulta_id UUID NOT NULL,
	coincidencia_id UUID,
	revision_previa_id UUID,
	resultado VARCHAR(40) NOT NULL,
	justificacion TEXT NOT NULL,
	actor_emisor VARCHAR(500) NOT NULL,
	actor_sujeto VARCHAR(200) NOT NULL,
	id UUID NOT NULL,
	creado_en TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_revision_cumplimiento_consulta UNIQUE (consulta_id, id),
	CONSTRAINT fk_revision_coincidencia FOREIGN KEY(consulta_id, coincidencia_id) REFERENCES coincidencia_lista (consulta_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_revision_previa FOREIGN KEY(consulta_id, revision_previa_id) REFERENCES revision_cumplimiento (consulta_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_revision_resultado CHECK (resultado IN ('DESCARTADA','IDENTIDAD_CORROBORADA','REQUIERE_INFORMACION')),
	FOREIGN KEY(consulta_id) REFERENCES consulta_lista (id) ON DELETE RESTRICT
)""",
)

FUNCIONES = r"""
CREATE FUNCTION listas_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro de % es inmutable', TG_TABLE_NAME;
END $$;

CREATE FUNCTION listas_crear_puntero() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO fuente_version_activa(fuente_id, version_id, revision) VALUES(NEW.id, NULL, 0);
    RETURN NEW;
END $$;

CREATE FUNCTION listas_proteger_recepcion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' OR OLD.estado IN ('RECIBIDA','FALLIDA') THEN
        RAISE EXCEPTION 'La recepción final conserva archivo y cargador originales';
    END IF;
    IF (NEW.actor_emisor,NEW.actor_sujeto,NEW.fuente_id) IS DISTINCT FROM (OLD.actor_emisor,OLD.actor_sujeto,OLD.fuente_id) THEN
        RAISE EXCEPTION 'No se modifica la identidad del cargador';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_proteger_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cantidad integer;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'No se eliminan versiones'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.estado <> 'EN_CONSTRUCCION' THEN RAISE EXCEPTION 'La versión debe construirse antes de sellarse'; END IF;
        RETURN NEW;
    END IF;
    IF OLD.estado IN ('VALIDA','BLOQUEADA') THEN
        IF OLD.estado = 'BLOQUEADA' OR NEW.estado <> 'BLOQUEADA'
           OR (to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado') THEN
            RAISE EXCEPTION 'El contenido sellado es inmutable';
        END IF;
    END IF;
    IF NEW.estado = 'VALIDA' THEN
        SELECT count(*) INTO cantidad FROM registro_lista WHERE version_id = NEW.id;
        IF cantidad = 0 OR cantidad <> NEW.cantidad_registros THEN
            RAISE EXCEPTION 'El conteo de registros no acredita importación completa';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM esquema_fuente WHERE id=NEW.esquema_id AND aprobado)
           OR NOT EXISTS(SELECT 1 FROM recepcion_fuente WHERE id=NEW.recepcion_id AND estado='RECIBIDA')
           OR NOT EXISTS(SELECT 1 FROM archivo_fuente WHERE id=NEW.archivo_contenido_id AND huella=NEW.huella_contenido) THEN
            RAISE EXCEPTION 'Falta esquema aprobado, recepción completa o integridad del original';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_proteger_datos_version() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE identificador uuid; identificador_anterior uuid; estado_version text;
BEGIN
    IF TG_TABLE_NAME IN ('registro_lista','relacion_registro') THEN
        IF TG_OP <> 'DELETE' THEN identificador := NEW.version_id; END IF;
        IF TG_OP <> 'INSERT' THEN identificador_anterior := OLD.version_id; END IF;
    ELSE
        IF TG_OP <> 'DELETE' THEN SELECT version_id INTO identificador FROM registro_lista WHERE id=NEW.registro_id; END IF;
        IF TG_OP <> 'INSERT' THEN SELECT version_id INTO identificador_anterior FROM registro_lista WHERE id=OLD.registro_id; END IF;
    END IF;
    FOR estado_version IN SELECT estado FROM version_fuente
        WHERE id IN (identificador, identificador_anterior) ORDER BY id FOR SHARE LOOP
        IF estado_version <> 'EN_CONSTRUCCION' THEN RAISE EXCEPTION 'Los datos de una versión sellada son inmutables'; END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_validar_cobertura() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE modo text; puntero fuente_version_activa; estado_version text;
BEGIN
    SELECT implementacion INTO modo FROM consulta_lista WHERE id=NEW.consulta_id;
    IF modo='archivos' AND NEW.version_id IS NOT NULL THEN
        SELECT * INTO puntero FROM fuente_version_activa WHERE fuente_id=NEW.fuente_id FOR SHARE;
        SELECT estado INTO estado_version FROM version_fuente WHERE id=NEW.version_id FOR SHARE;
        IF puntero.version_id IS DISTINCT FROM NEW.version_id OR puntero.revision IS DISTINCT FROM NEW.revision_activa
           OR estado_version IS DISTINCT FROM 'VALIDA' THEN
            RAISE EXCEPTION 'Solo se fija una versión válida y activa';
        END IF;
    ELSIF modo <> 'archivos' AND NEW.version_id IS NOT NULL THEN
        RAISE EXCEPTION 'No se atribuye una versión local al proveedor externo o simulado';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_validar_coincidencia() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_fijada uuid;
BEGIN
    SELECT version_id INTO version_fijada FROM consulta_fuente WHERE id=NEW.consulta_fuente_id AND consulta_id=NEW.consulta_id;
    IF version_fijada IS DISTINCT FROM NEW.version_id THEN
        RAISE EXCEPTION 'La coincidencia debe conservar la versión fijada, incluso frente a nulos';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_comprobar_evento() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM fuente_version_activa WHERE fuente_id=NEW.fuente_id
                  AND version_id=NEW.destino_id AND revision=NEW.revision_nueva) THEN
        RAISE EXCEPTION 'Evento de activación sin cambio de puntero en la misma transacción';
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION listas_comprobar_evento_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado IS DISTINCT FROM OLD.estado AND NOT EXISTS(
        SELECT 1 FROM evento_version WHERE version_id=NEW.id AND estado_anterior=OLD.estado
          AND estado_nuevo=NEW.estado AND creado_en >= transaction_timestamp()) THEN
        RAISE EXCEPTION 'Transición de versión sin auditoría';
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION listas_proteger_consulta() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'No se elimina el historial de consultas'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.estado <> 'PENDIENTE' THEN RAISE EXCEPTION 'La consulta se registra antes de cerrarse'; END IF;
        RETURN NEW;
    END IF;
    IF OLD.estado NOT IN ('PENDIENTE','EN_CURSO') THEN RAISE EXCEPTION 'La consulta final es inmutable'; END IF;
    IF (to_jsonb(NEW) - ARRAY['estado','conclusion','resultado','finalizada_en'])
        IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['estado','conclusion','resultado','finalizada_en']) THEN
        RAISE EXCEPTION 'No se modifica el contexto admitido';
    END IF;
    IF OLD.estado='EN_CURSO' AND NEW.estado='PENDIENTE' THEN RAISE EXCEPTION 'No se reabre la consulta'; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_proteger_hijos_consulta() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE identificador uuid; anterior uuid; estado_consulta text;
BEGIN
    IF TG_OP <> 'DELETE' THEN identificador := NEW.consulta_id; END IF;
    IF TG_OP <> 'INSERT' THEN anterior := OLD.consulta_id; END IF;
    FOR estado_consulta IN SELECT estado FROM consulta_lista WHERE id IN (identificador, anterior) ORDER BY id FOR SHARE LOOP
        IF estado_consulta NOT IN ('PENDIENTE','EN_CURSO') THEN RAISE EXCEPTION 'El resultado histórico es inmutable'; END IF;
    END LOOP;
    IF TG_TABLE_NAME='consulta_fuente' AND TG_OP='UPDATE' AND
       (to_jsonb(NEW) - 'estado') IS DISTINCT FROM (to_jsonb(OLD) - 'estado') THEN
        RAISE EXCEPTION 'La cobertura fijada es inmutable';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_comprobar_cierre() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE consulta consulta_lista; cantidad integer; hay_candidatos boolean;
BEGIN
    SELECT * INTO consulta FROM consulta_lista WHERE id=NEW.id;
    IF consulta.estado IN ('COMPLETADA','PARCIAL') THEN
        PERFORM v.id FROM version_fuente v
            WHERE v.id IN (SELECT version_id FROM consulta_fuente WHERE consulta_id=consulta.id)
            ORDER BY v.id FOR SHARE;
        SELECT count(*) INTO cantidad FROM evidencia_consulta WHERE consulta_id=consulta.id AND tipo='INFORME_INTERNO';
        IF cantidad <> 1 OR consulta.resultado IS NULL THEN RAISE EXCEPTION 'El cierre requiere resultado e informe custodiado'; END IF;
        IF consulta.implementacion='archivos' AND EXISTS(
            SELECT 1 FROM consulta_fuente c LEFT JOIN version_fuente v ON v.id=c.version_id
            WHERE c.consulta_id=consulta.id AND c.estado='CONSULTADA' AND
                (v.id IS NULL OR v.estado <> 'VALIDA' OR c.revision_activa IS NULL)) THEN
            RAISE EXCEPTION 'Una versión inválida no permite cerrar el resultado';
        END IF;
    END IF;
    IF consulta.estado='COMPLETADA' THEN
        IF NOT EXISTS(SELECT 1 FROM consulta_fuente WHERE consulta_id=consulta.id AND requerida)
           OR EXISTS(SELECT 1 FROM consulta_fuente WHERE consulta_id=consulta.id AND requerida AND estado <> 'CONSULTADA') THEN
            RAISE EXCEPTION 'Cobertura incompleta';
        END IF;
        hay_candidatos := EXISTS(SELECT 1 FROM coincidencia_lista WHERE consulta_id=consulta.id)
                         OR EXISTS(SELECT 1 FROM hallazgo_proveedor WHERE consulta_id=consulta.id);
        IF (hay_candidatos AND consulta.conclusion <> 'CON_CANDIDATOS') OR
           (NOT hay_candidatos AND consulta.conclusion <> 'SIN_CANDIDATOS') THEN
            RAISE EXCEPTION 'Conclusión contradictoria';
        END IF;
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION listas_validar_aprobacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; cargador recepcion_fuente;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT r.* INTO cargador FROM recepcion_fuente r JOIN version_fuente v ON v.recepcion_id=r.id WHERE v.id=comparacion.destino_id;
    IF NEW.decision='APROBADA' AND NEW.actor_emisor=cargador.actor_emisor AND NEW.actor_sujeto=cargador.actor_sujeto THEN
        RAISE EXCEPTION 'El cargador no puede aprobar su carga';
    END IF;
    IF (NEW.decision='REVOCADA') <> (NEW.revoca_revision_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Revocación sin aprobación de origen';
    END IF;
    IF NEW.decision='REVOCADA' AND NOT EXISTS(SELECT 1 FROM revision_comparacion WHERE id=NEW.revoca_revision_id AND decision='APROBADA') THEN
        RAISE EXCEPTION 'Solo se revoca una aprobación';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_validar_evento_activacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE comparacion comparacion_version; aprobacion revision_comparacion;
BEGIN
    SELECT * INTO comparacion FROM comparacion_version WHERE id=NEW.comparacion_id FOR UPDATE;
    SELECT * INTO aprobacion FROM revision_comparacion WHERE id=NEW.aprobacion_id;
    IF comparacion.fuente_id IS DISTINCT FROM NEW.fuente_id OR comparacion.base_id IS DISTINCT FROM NEW.anterior_id
       OR comparacion.destino_id IS DISTINCT FROM NEW.destino_id OR comparacion.revision_base <> NEW.revision_anterior
       OR aprobacion.decision IS DISTINCT FROM 'APROBADA'
       OR EXISTS(SELECT 1 FROM revision_comparacion WHERE revoca_revision_id=NEW.aprobacion_id) THEN
        RAISE EXCEPTION 'Comparación o aprobación no vigente para la activación';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM version_fuente WHERE id=NEW.destino_id AND estado='VALIDA') THEN
        RAISE EXCEPTION 'Destino no válido';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION listas_comprobar_puntero() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        IF NEW.revision <> 0 OR NEW.version_id IS NOT NULL THEN RAISE EXCEPTION 'Puntero inicial inválido'; END IF;
    ELSE
        IF NEW.fuente_id <> OLD.fuente_id OR NEW.revision <> OLD.revision+1 THEN RAISE EXCEPTION 'Revisión de puntero inválida'; END IF;
        IF NOT EXISTS(SELECT 1 FROM evento_activacion WHERE fuente_id=NEW.fuente_id
                      AND revision_nueva=NEW.revision AND destino_id=NEW.version_id
                      AND anterior_id IS NOT DISTINCT FROM OLD.version_id) THEN
            RAISE EXCEPTION 'Cambio de activa sin evento en la misma transacción';
        END IF;
    END IF;
    RETURN NULL;
END $$;
"""

INMUTABLES = (
    "archivo_fuente", "politica_listas", "esquema_fuente", "comparacion_version", "revision_comparacion",
    "evento_activacion", "evento_version", "comprobacion_fuente", "evidencia_consulta",
    "revision_cumplimiento", "evento_consulta",
)
DATOS_VERSION = ("registro_lista", "nombre_registro", "identificador_registro", "direccion_registro", "atributo_registro", "relacion_registro")
HIJOS_CONSULTA = ("consulta_fuente", "coincidencia_lista", "hallazgo_proveedor", "borrador_consulta")


def upgrade():
    for sentencia in SENTENCIAS:
        op.execute(sa.text(sentencia))
    op.execute(sa.text(FUNCIONES))
    for tabla in INMUTABLES:
        op.execute(f"CREATE TRIGGER proteger_{tabla} BEFORE UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_inmutable()")
    for tabla in DATOS_VERSION:
        op.execute(f"CREATE TRIGGER proteger_{tabla} BEFORE INSERT OR UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_proteger_datos_version()")
    for tabla in HIJOS_CONSULTA:
        op.execute(f"CREATE TRIGGER proteger_{tabla} BEFORE INSERT OR UPDATE OR DELETE ON {tabla} FOR EACH ROW EXECUTE FUNCTION listas_proteger_hijos_consulta()")
    op.execute("CREATE TRIGGER proteger_recepcion BEFORE UPDATE OR DELETE ON recepcion_fuente FOR EACH ROW EXECUTE FUNCTION listas_proteger_recepcion()")
    op.execute("CREATE TRIGGER crear_puntero AFTER INSERT ON fuente_lista FOR EACH ROW EXECUTE FUNCTION listas_crear_puntero()")
    op.execute("CREATE TRIGGER proteger_version BEFORE INSERT OR UPDATE OR DELETE ON version_fuente FOR EACH ROW EXECUTE FUNCTION listas_proteger_version()")
    op.execute("CREATE TRIGGER proteger_consulta BEFORE INSERT OR UPDATE OR DELETE ON consulta_lista FOR EACH ROW EXECUTE FUNCTION listas_proteger_consulta()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_cierre AFTER INSERT OR UPDATE ON consulta_lista DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_cierre()")
    op.execute("CREATE TRIGGER validar_cobertura BEFORE INSERT ON consulta_fuente FOR EACH ROW EXECUTE FUNCTION listas_validar_cobertura()")
    op.execute("CREATE TRIGGER validar_coincidencia BEFORE INSERT OR UPDATE ON coincidencia_lista FOR EACH ROW EXECUTE FUNCTION listas_validar_coincidencia()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_evento AFTER INSERT ON evento_activacion DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_evento()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_evento_version AFTER UPDATE ON version_fuente DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_evento_version()")
    op.execute("CREATE TRIGGER validar_aprobacion BEFORE INSERT ON revision_comparacion FOR EACH ROW EXECUTE FUNCTION listas_validar_aprobacion()")
    op.execute("CREATE TRIGGER validar_activacion BEFORE INSERT ON evento_activacion FOR EACH ROW EXECUTE FUNCTION listas_validar_evento_activacion()")
    op.execute("CREATE CONSTRAINT TRIGGER comprobar_puntero AFTER INSERT OR UPDATE ON fuente_version_activa DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION listas_comprobar_puntero()")
    op.execute("CREATE TRIGGER conservar_puntero BEFORE DELETE ON fuente_version_activa FOR EACH ROW EXECUTE FUNCTION listas_inmutable()")


def downgrade():
    conexion = op.get_bind()
    for tabla in TABLAS:
        if conexion.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {tabla})")).scalar():
            raise RuntimeError("No se revierte el esquema de listas con datos: se debe preservar el historial")
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)
    for funcion in (
        "listas_inmutable", "listas_crear_puntero", "listas_proteger_recepcion", "listas_proteger_version", "listas_proteger_datos_version",
        "listas_proteger_consulta", "listas_proteger_hijos_consulta", "listas_comprobar_cierre",
        "listas_validar_aprobacion", "listas_validar_evento_activacion", "listas_comprobar_puntero",
        "listas_validar_cobertura", "listas_validar_coincidencia", "listas_comprobar_evento", "listas_comprobar_evento_version",
    ):
        op.execute(f"DROP FUNCTION {funcion}()")
