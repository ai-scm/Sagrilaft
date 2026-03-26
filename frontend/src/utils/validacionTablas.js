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

const esCampoVacio = (valor) =>
  valor === undefined || valor === null || String(valor).trim() === '';

/** Etiquetas legibles para mensajes de error (fuente única de verdad). */
const ETIQUETAS_CAMPO = {
  cargo:        'Cargo',
  nombre:       'Nombre',
  porcentaje:   '% Participación',
  tipo_id:      'Tipo ID',
  numero_id:    'Número ID',
  es_pep:       '¿PEP?',
  vinculos_pep: 'Vínculos PEP',
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
    label:             'Junta Directiva y Representantes',
    errorKey:          'junta_directiva_tabla',
    errorKeyFilas:     'junta_directiva_filas',
    camposObligatorios: ['cargo', 'nombre', 'tipo_id', 'numero_id', 'es_pep'],
    reglasCondicionales: [
      (fila) =>
        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
          : null,
    ],
  },

  accionistas: {
    label:             'Composición Accionaria',
    errorKey:          'accionistas_tabla',
    errorKeyFilas:     'accionistas_filas',
    camposObligatorios: ['nombre', 'porcentaje', 'tipo_id', 'numero_id', 'es_pep'],
    reglasCondicionales: [
      (fila) =>
        !esCampoVacio(fila.porcentaje) && Number(fila.porcentaje) <= 5
          ? { campo: 'porcentaje', mensaje: 'El % de participación debe ser mayor al 5%' }
          : null,
      (fila) =>
        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
          : null,
    ],
  },

  beneficiarios: {
    label:             'Beneficiario Final',
    errorKey:          'beneficiarios_tabla',
    errorKeyFilas:     'beneficiarios_filas',
    camposObligatorios: ['nombre', 'porcentaje', 'tipo_id', 'numero_id', 'es_pep'],
    reglasCondicionales: [
      (fila) =>
        !esCampoVacio(fila.tipo_id) && String(fila.tipo_id).toUpperCase() === 'NIT'
          ? { campo: 'tipo_id', mensaje: 'El Tipo ID del beneficiario final no puede ser NIT (debe ser CC, CE o PAS)' }
          : null,
      (fila) =>
        fila.es_pep === 'si' && esCampoVacio(fila.vinculos_pep)
          ? { campo: 'vinculos_pep', mensaje: 'Vínculos PEP es obligatorio cuando ¿PEP? es "Sí"' }
          : null,
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
 * Valida una tabla completa.
 * @returns {{ erroresFilas: Array<object|null>, mensajeTabla: string|null }}
 */
const validarTabla = (filas, esquema) => {
  const erroresFilas = [];
  let filasDiligenciadas = 0;
  let filasValidas = 0;

  for (const fila of filas) {
    if (esFilaVacia(fila, esquema.camposObligatorios)) {
      erroresFilas.push(null);
      continue;
    }

    filasDiligenciadas++;
    const erroresFila = validarFila(fila, esquema);
    const esValida = Object.keys(erroresFila).length === 0;

    erroresFilas.push(esValida ? null : erroresFila);
    if (esValida) filasValidas++;
  }

  let mensajeTabla = null;
  if (filasDiligenciadas === 0) {
    mensajeTabla = `Debe registrar al menos un registro en ${esquema.label}`;
  } else if (filasValidas < filasDiligenciadas) {
    mensajeTabla = `Complete todos los campos obligatorios en ${esquema.label}`;
  }

  return { erroresFilas, mensajeTabla };
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
    const { erroresFilas, mensajeTabla } = validarTabla(filas, esquema);
    if (mensajeTabla) {
      errores[esquema.errorKey]      = mensajeTabla;
      errores[esquema.errorKeyFilas] = erroresFilas;
    }
  }

  return errores;
};

/** Claves de error del paso 4 (útil para limpiar errores cuando cambia una tabla). */
export const CLAVES_ERROR_PASO4 = Object.values(ESQUEMAS_TABLA).flatMap((e) => [
  e.errorKey,
  e.errorKeyFilas,
]);
