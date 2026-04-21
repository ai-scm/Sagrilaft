/**
 * validacionTablas.js
 *
 * Motor de validación para las tablas del Paso 4 (Junta Directiva, Accionistas,
 * Beneficiarios Finales).
 *
 * SOLID:
 *   S — cada función tiene una única responsabilidad
 *   O — nuevas tablas o reglas se agregan en ESQUEMAS_TABLA sin tocar el motor
 *   D — el motor depende de esquemas abstractos, no de tablas concretas
 *
 * DRY — la lógica de validación de filas y tablas es genérica y reutilizable.
 */

// ─── Primitivas ──────────────────────────────────────────────────────────────

export {
  UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA,
  UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL,
  PORCENTAJE_MAXIMO_PERMITIDO,
  LONGITUD_MAXIMA_ID,
  LONGITUD_TELEFONO,
} from './constantes';


const esCampoVacio = (valor) =>
  valor === undefined || valor === null || String(valor).trim() === '';

const REGEX_NUMERO_ID = new RegExp(`^[a-zA-Z0-9]{1,${LONGITUD_MAXIMA_ID}}$`);

const reglaNumeroIdAlfanumerico = (fila) =>
  !esCampoVacio(fila.numero_id) && !REGEX_NUMERO_ID.test(fila.numero_id)
    ? { campo: 'numero_id', mensaje: `El Número ID debe contener entre 1 y ${LONGITUD_MAXIMA_ID} caracteres alfanuméricos (letras/números sin espacios)` }
    : null;

/** Etiquetas legibles para mensajes de error (fuente única de verdad). */
const ETIQUETAS_CAMPO = {
  cargo:                  'Cargo',
  nombre:                 'Nombre',
  porcentaje:             '% Participación',
  porcentaje_control:     '% Control',
  tipo_id:                'Tipo ID',
  numero_id:              'Número ID',
  es_pep:                 '¿PEP?',
  vinculos_pep:           'Vínculos PEP',
  nombre_establecimiento: 'Nombre del establecimiento',
  persona_contacto:       'Persona a contactar',
  telefono:               'Teléfono',
  ciudad:                 'Ciudad',
  entidad:                'Entidad',
  producto:               'Producto',
  entidad_bancaria:       'Entidad Bancaria',
  ciudad_oficina:         'Ciudad / Oficina',
  tipo_cuenta:            'Tipo de Cuenta',
  numero_cuenta:          'Número de Cuenta',
};

const mensajeObligatorio = (campo) =>
  `${ETIQUETAS_CAMPO[campo] ?? campo} es obligatorio`;

// ─── Esquemas declarativos (OCP) ─────────────────────────────────────────────

/**
 * Cada entrada define:
 *   label              — nombre legible de la sección
 *   errorKey           — clave en el mapa de errores para el mensaje de tabla
 *   errorKeyFilas      — clave para el array de errores por fila
 *   camposObligatorios — campos que siempre deben tener valor
 *   reglasCondicionales — reglas extra; retornan { campo, mensaje } o null
 */
export const ESQUEMAS_TABLA = {
  juntaDirectiva: {
    label:              'Junta Directiva y Representantes',
    errorKey:           'junta_directiva_tabla',
    errorKeyFilas:      'junta_directiva_filas',
    errorKeySuma:       null,
    camposObligatorios: ['cargo', 'nombre', 'tipo_id', 'numero_id', 'es_pep'],
    reglasCondicionales: [
      reglaNumeroIdAlfanumerico,
      (fila) =>
        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
          : null,
    ],
    reglasGrupales: [],
  },

	  accionistas: {
	    label:             'Composición Accionaria',
	    errorKey:          'accionistas_tabla',
	    errorKeyFilas:     'accionistas_filas',
	    errorKeySuma:      'accionistas_suma',
	    camposObligatorios: ['nombre', 'porcentaje', 'tipo_id', 'numero_id', 'es_pep'],
	    reglasCondicionales: [
	      reglaNumeroIdAlfanumerico,
	      (fila) =>
	        !esCampoVacio(fila.porcentaje) && Number(fila.porcentaje) <= UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA
	          ? { campo: 'porcentaje', mensaje: `El % de participación debe ser mayor al ${UMBRAL_MINIMO_PARTICIPACION_ACCIONISTA}%` }
	          : null,
	      (fila) =>
	        !esCampoVacio(fila.porcentaje) && Number(fila.porcentaje) >= PORCENTAJE_MAXIMO_PERMITIDO
	          ? { campo: 'porcentaje', mensaje: `El % de participación no puede ser igual o superior al ${PORCENTAJE_MAXIMO_PERMITIDO}%` }
	          : null,
	      (fila) =>
	        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
	          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
	          : null,
	    ],
	    reglasGrupales: [
	      (filasActivas) => {
	        const total = sumarPorcentajes(filasActivas);
	        return total > PORCENTAJE_MAXIMO_PERMITIDO
	          ? `La suma de participaciones accionarias es ${total.toFixed(2)}%, lo que excede el ${PORCENTAJE_MAXIMO_PERMITIDO}% permitido`
	          : null;
	      },
	    ],
	  },

	  beneficiarios: {
	    label:             'Beneficiario Final',
	    errorKey:          'beneficiarios_tabla',
	    errorKeyFilas:     'beneficiarios_filas',
	    errorKeySuma:      'beneficiarios_suma',
	    camposObligatorios: ['nombre', 'porcentaje', 'tipo_id', 'numero_id', 'es_pep'],
	    reglasCondicionales: [
	      reglaNumeroIdAlfanumerico,
	      (fila) =>
	        !esCampoVacio(fila.porcentaje) && Number(fila.porcentaje) <= UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL
	          ? { campo: 'porcentaje', mensaje: `El % de control debe ser mayor al ${UMBRAL_MINIMO_CONTROL_BENEFICIARIO_FINAL}%` }
	          : null,
	      (fila) =>
	        !esCampoVacio(fila.porcentaje) && Number(fila.porcentaje) >= PORCENTAJE_MAXIMO_PERMITIDO
	          ? { campo: 'porcentaje', mensaje: `El % de control no puede ser igual o superior al ${PORCENTAJE_MAXIMO_PERMITIDO}%` }
	          : null,
	      (fila) =>
	        !esCampoVacio(fila.tipo_id) && String(fila.tipo_id).toUpperCase() === 'NIT'
	          ? { campo: 'tipo_id', mensaje: 'El Tipo ID del beneficiario final no puede ser NIT (debe ser CC, CE o PAS)' }
	          : null,
      (fila) =>
        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
          : null,
    ],
	    reglasGrupales: [
	      (filasActivas) => {
	        const total = sumarPorcentajes(filasActivas);
	        return total > PORCENTAJE_MAXIMO_PERMITIDO
	          ? `La suma de porcentajes de control es ${total.toFixed(2)}%, lo que excede el ${PORCENTAJE_MAXIMO_PERMITIDO}% permitido`
	          : null;
	      },
	    ],
	  },
};

// ─── Motor genérico ──────────────────────────────────────────────────────────

/**
 * Valida una sola fila contra un esquema.
 * @returns {{ [campo: string]: string }} — mapa de errores; vacío si la fila es válida.
 */
const validarFila = (fila, esquema) => {
  const erroresFila = {};

  for (const campo of esquema.camposObligatorios) {
    if (esCampoVacio(fila[campo])) {
      erroresFila[campo] = mensajeObligatorio(campo);
    }
  }

  for (const regla of esquema.reglasCondicionales) {
    const resultado = regla(fila);
    if (resultado && !erroresFila[resultado.campo]) {
      erroresFila[resultado.campo] = resultado.mensaje;
    }
  }

  return erroresFila;
};

/** Una fila está vacía si ninguno de sus campos obligatorios tiene valor. */
const esFilaVacia = (fila, camposObligatorios) =>
  camposObligatorios.every((campo) => esCampoVacio(fila[campo]));

/**
 * Suma los porcentajes numéricos de un conjunto de filas con datos.
 * Ignora valores no numéricos para no acumular NaN.
 */
const sumarPorcentajes = (filas) =>
  filas.reduce((acumulado, fila) => {
    const valor = Number(fila.porcentaje);
    return acumulado + (Number.isFinite(valor) ? valor : 0);
  }, 0);

/**
 * Valida una tabla completa: primero campo a campo (por fila),
 * luego reglas grupales que operan sobre el conjunto de filas activas.
 *
 * @returns {{
 *   erroresFilas:  Array<object|null>,
 *   mensajeTabla:  string|null,
 *   errorGrupal:   string|null
 * }}
 */
const validarTabla = (filas, esquema) => {
  const erroresFilas   = [];
  const filasActivas   = [];   // filas con al menos un campo diligenciado
  let filasValidas     = 0;

  for (const fila of filas) {
    if (esFilaVacia(fila, esquema.camposObligatorios)) {
      erroresFilas.push(null);
      continue;
    }

    filasActivas.push(fila);
    const erroresFila = validarFila(fila, esquema);
    const esValida    = Object.keys(erroresFila).length === 0;

    erroresFilas.push(esValida ? null : erroresFila);
    if (esValida) filasValidas++;
  }

  let mensajeTabla = null;
  if (filasActivas.length === 0) {
    mensajeTabla = `Debe registrar al menos un registro en ${esquema.label}`;
  } else if (filasValidas < filasActivas.length) {
    mensajeTabla = `Complete todos los campos obligatorios en ${esquema.label}`;
  }

  // Reglas grupales: se evalúan sobre el conjunto completo de filas activas.
  // Se ejecutan siempre (independientemente de errores por fila) para que el
  // usuario vea el problema de suma incluso si los campos individuales son válidos.
  let errorGrupal = null;
  for (const regla of esquema.reglasGrupales ?? []) {
    errorGrupal = regla(filasActivas);
    if (errorGrupal) break;
  }

  return { erroresFilas, mensajeTabla, errorGrupal };
};

// ─── Punto de entrada para el paso 4 ─────────────────────────────────────────

/**
 * Valida las tres tablas del Paso 4.
 * Solo aplica a Persona Jurídica; retorna {} para Persona Natural.
 *
 * @param {{ juntaDirectiva, accionistas, beneficiarios, tipoPersona }} param0
 * @returns {{ [key: string]: any }} — mapa listo para aplicarErrores()
 */
export const validarTablasPaso4 = ({ juntaDirectiva, accionistas, beneficiarios, tipoPersona }) => {
  if (tipoPersona === 'natural') return {};

  const errores = {};

  const tablas = [
    { filas: juntaDirectiva, esquema: ESQUEMAS_TABLA.juntaDirectiva },
    { filas: accionistas,    esquema: ESQUEMAS_TABLA.accionistas    },
    { filas: beneficiarios,  esquema: ESQUEMAS_TABLA.beneficiarios  },
  ];

  for (const { filas, esquema } of tablas) {
    const { erroresFilas, mensajeTabla, errorGrupal } = validarTabla(filas, esquema);
    if (mensajeTabla) {
      errores[esquema.errorKey]      = mensajeTabla;
      errores[esquema.errorKeyFilas] = erroresFilas;
    }
    if (errorGrupal && esquema.errorKeySuma) {
      errores[esquema.errorKeySuma] = errorGrupal;
    }
  }

  return errores;
};

/** Claves de error del paso 4 (útil para limpiar errores cuando cambia una tabla). */
export const CLAVES_ERROR_PASO4 = Object.values(ESQUEMAS_TABLA).flatMap((e) =>
  [e.errorKey, e.errorKeyFilas, e.errorKeySuma].filter(Boolean),
);

// ─── Esquemas y validación del paso 6 ────────────────────────────────────────

const ESQUEMAS_PASO6 = {
  referenciasComerciales: {
    label:              'Referencias Comerciales',
    errorKey:           'referencias_comerciales_tabla',
    errorKeyFilas:      'referencias_comerciales_filas',
    camposObligatorios: ['nombre_establecimiento', 'persona_contacto', 'telefono', 'ciudad'],
    reglasCondicionales: [
      (fila) =>
        !esCampoVacio(fila.telefono) && String(fila.telefono).length !== LONGITUD_TELEFONO
          ? { campo: 'telefono', mensaje: `Debe tener exactamente ${LONGITUD_TELEFONO} dígitos` }
          : null,
    ],
  },
  referenciasBancarias: {
    label:              'Referencias Bancarias',
    errorKey:           'referencias_bancarias_tabla',
    errorKeyFilas:      'referencias_bancarias_filas',
    camposObligatorios: ['entidad', 'producto'],
    reglasCondicionales: [],
  },
};

/**
 * Valida las tablas del Paso 6 (Referencias Comerciales y Bancarias).
 * Reutiliza el mismo motor genérico de validarTabla.
 */
export const validarTablasPaso6 = ({ referenciasComerciales, referenciasBancarias }) => {
  const errores = {};

  const tablas = [
    { filas: referenciasComerciales, esquema: ESQUEMAS_PASO6.referenciasComerciales },
    { filas: referenciasBancarias,   esquema: ESQUEMAS_PASO6.referenciasBancarias   },
  ];

  for (const { filas, esquema } of tablas) {
    const { erroresFilas, mensajeTabla } = validarTabla(filas, esquema);
    if (mensajeTabla) {
      errores[esquema.errorKey]      = mensajeTabla;
      errores[esquema.errorKeyFilas] = erroresFilas;
    }
  }

  return errores;
};

/** Claves de error del paso 6. */
export const CLAVES_ERROR_PASO6 = Object.values(ESQUEMAS_PASO6).flatMap((e) => [
  e.errorKey,
  e.errorKeyFilas,
]);

// ─── Esquemas y validación del paso 7 ────────────────────────────────────────

const ESQUEMAS_PASO7 = {
  infoBancariaPagos: {
    label:              'Información Bancaria para Pagos',
    errorKey:           'info_bancaria_pagos_tabla',
    errorKeyFilas:      'info_bancaria_pagos_filas',
    camposObligatorios: ['entidad_bancaria', 'ciudad_oficina', 'tipo_cuenta', 'numero_cuenta'],
    reglasCondicionales: [],
  },
};

/**
 * Valida la tabla de Información Bancaria para Pagos del Paso 7.
 * Reutiliza el mismo motor genérico de validarTabla.
 */
export const validarTablasPaso7 = ({ infoBancariaPagos }) => {
  const errores = {};
  const esquema = ESQUEMAS_PASO7.infoBancariaPagos;
  const { erroresFilas, mensajeTabla } = validarTabla(infoBancariaPagos, esquema);
  if (mensajeTabla) {
    errores[esquema.errorKey]      = mensajeTabla;
    errores[esquema.errorKeyFilas] = erroresFilas;
  }
  return errores;
};

/** Claves de error del paso 7. */
export const CLAVES_ERROR_PASO7 = Object.values(ESQUEMAS_PASO7).flatMap((e) => [
  e.errorKey,
  e.errorKeyFilas,
]);
