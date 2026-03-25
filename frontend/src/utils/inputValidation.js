/**
 * Reglas de validación de input centralizadas.
 *
 * Fuente única de verdad para restricciones de campos numéricos.
 * Consumido por FormField (bloqueo en tiempo real) y useFormValidacion (errores al avanzar).
 *
 * Para agregar reglas a un campo nuevo, solo editar REGLAS_INPUT.
 */

/** Teclas de control que siempre se permiten en inputs numéricos. */
const TECLAS_CONTROL = [
  'Backspace', 'Delete', 'Tab',
  'ArrowLeft', 'ArrowRight', 'Home', 'End',
];

/** Bloquea teclas no numéricas. Permite atajos de teclado (Ctrl/Cmd). */
export const onlyNumericKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (!TECLAS_CONTROL.includes(e.key) && !/^\d$/.test(e.key)) {
    e.preventDefault();
  }
};

/** Bloquea pegado de texto que contenga caracteres no numéricos. */
export const onlyNumericPaste = (e) => {
  if (!/^\d+$/.test(e.clipboardData.getData('text'))) {
    e.preventDefault();
  }
};

/** Bloquea el signo negativo, '+' y notación científica 'e' en campos numéricos positivos. */
const blockNegativeKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (['-', '+', 'e', 'E'].includes(e.key)) e.preventDefault();
};

/**
 * Reglas por nombre de campo.
 *   soloNumericos  → bloquea teclas y paste no numéricos.
 *   longitudExacta → valida longitud exacta en N dígitos.
 *   longitudMaxima → valida longitud máxima de N dígitos.
 *   soloPositivo   → bloquea signo negativo; min=0 en el input.
 */
export const REGLAS_INPUT = {
  numero_identificacion:    { soloNumericos: true },
  numero_doc_representante: { soloNumericos: true },
  telefono:                 { soloNumericos: true, longitudExacta: 10 },
  telefono_representante:   { soloNumericos: true, longitudExacta: 10 },
  codigo_ciiu:              { soloNumericos: true, longitudMaxima: 4 },
  codigo_ica:               { soloNumericos: true, longitudMaxima: 4 },
  ingresos_mensuales:       { soloPositivo: true },
  otros_ingresos:           { soloPositivo: true },
  egresos_mensuales:        { soloPositivo: true },
  total_activos:            { soloPositivo: true },
  total_pasivos:            { soloPositivo: true },
  patrimonio:               { soloPositivo: true },
};

/**
 * Retorna las props de input derivadas de las reglas del campo.
 * Usado por FormField para aplicar restricciones automáticamente.
 */
export function getInputProps(fieldName) {
  const reglas = REGLAS_INPUT[fieldName];
  if (!reglas) return {};

  const props = {};
  if (reglas.soloNumericos) {
    props.onKeyDown = onlyNumericKeyDown;
    props.onPaste   = onlyNumericPaste;
    props.inputMode = 'numeric';
  }
  if (reglas.soloPositivo) {
    props.onKeyDown = blockNegativeKeyDown;
    props.min       = 0;
  }
  if (reglas.longitudExacta) {
    props.maxLength = reglas.longitudExacta;
  }
  if (reglas.longitudMaxima) {
    props.maxLength = reglas.longitudMaxima;
  }
  return props;
}

/**
 * Valida las reglas especiales para los campos presentes en un paso.
 * Retorna un mapa campo → mensaje de error.
 */
export function validarReglasEspeciales(formData, camposDePaso) {
  const errores = {};
  for (const campo of camposDePaso) {
    const reglas = REGLAS_INPUT[campo];
    if (!reglas) continue;

    const valor = String(formData[campo] ?? '').trim();
    if (!valor) continue;

    if (reglas.longitudExacta && valor.length !== reglas.longitudExacta) {
      errores[campo] = `Debe tener exactamente ${reglas.longitudExacta} dígitos`;
    }
    if (reglas.longitudMaxima && valor.length > reglas.longitudMaxima) {
      errores[campo] = `Máximo ${reglas.longitudMaxima} dígitos`;
    }
    if (reglas.soloPositivo && parseFloat(valor) < 0) {
      errores[campo] = 'El valor debe ser mayor o igual a 0';
    }
  }
  return errores;
}
