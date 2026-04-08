/**
 * Reglas de validación de input centralizadas.
 *
 * Fuente única de verdad para restricciones de campos numéricos.
 * Consumido por FormField (bloqueo en tiempo real) y useFormValidacion (errores al avanzar).
 *
 * Para agregar reglas a un campo nuevo, solo editar REGLAS_INPUT.
 */

/** Teclas de control que siempre se permiten en cualquier input restringido. */
const TECLAS_CONTROL = [
  'Backspace', 'Delete', 'Tab',
  'ArrowLeft', 'ArrowRight', 'Home', 'End',
];

// ─── Solo numérico ────────────────────────────────────────────────────────────

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

// ─── Solo texto (letras, tildes, espacios, guiones, puntos) ──────────────────

const REGEX_CHAR_TEXTO = /^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'.\-,]$/;

/** Bloquea dígitos y símbolos no textuales. */
export const onlyTextKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (!TECLAS_CONTROL.includes(e.key) && !REGEX_CHAR_TEXTO.test(e.key)) {
    e.preventDefault();
  }
};

/** Bloquea pegado que contenga caracteres no textuales. */
export const onlyTextPaste = (e) => {
  if (!/^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'.\-,]+$/.test(e.clipboardData.getData('text'))) {
    e.preventDefault();
  }
};

// ─── Alfanumérico (letras, números, espacios, guiones, puntos) ────────────────

const REGEX_CHAR_ALFANUMERICO = /^[a-zA-Z0-9áéíóúÁÉÍÓÚüÜñÑ\s'.\-,]$/;

/** Bloquea símbolos no alfanuméricos. */
export const onlyAlphanumericKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (!TECLAS_CONTROL.includes(e.key) && !REGEX_CHAR_ALFANUMERICO.test(e.key)) {
    e.preventDefault();
  }
};

/** Bloquea pegado que contenga símbolos no alfanuméricos. */
export const onlyAlphanumericPaste = (e) => {
  if (!/^[a-zA-Z0-9áéíóúÁÉÍÓÚüÜñÑ\s'.\-,]+$/.test(e.clipboardData.getData('text'))) {
    e.preventDefault();
  }
};

// ─── Alfanumérico Estricto (solo letras A-Z, a-z y números 0-9) ───────────────

const REGEX_CHAR_ALFANUMERICO_ESTRICTO = /^[a-zA-Z0-9]$/;

/** Bloquea cualquier carácter que no sea una letra no acentuada o número. */
export const onlyAlphanumericStrictKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (!TECLAS_CONTROL.includes(e.key) && !REGEX_CHAR_ALFANUMERICO_ESTRICTO.test(e.key)) {
    e.preventDefault();
  }
};

/** Bloquea pegado que contenga caracteres diferentes a letras no acentuadas o números. */
export const onlyAlphanumericStrictPaste = (e) => {
  if (!/^[a-zA-Z0-9]+$/.test(e.clipboardData.getData('text'))) {
    e.preventDefault();
  }
};

/** Bloquea el signo negativo, '+' y notación científica 'e' en campos numéricos positivos. */
const blockNegativeKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (['-', '+', 'e', 'E'].includes(e.key)) e.preventDefault();
};

/**
 * Expresión regular para validar correos electrónicos.
 *
 * Acepta:   usuario@dominio.com  |  nombre.apellido@empresa.co  |  user+tag@sub.domain.org
 * Rechaza:  brayar  |  @sin-usuario  |  sin-arroba.com  |  usuario@  |  usuario@dominio
 *
 * Desglose:
 *   ^[a-zA-Z0-9._%+\-]+   → parte local: letras, números y caracteres especiales permitidos
 *   @                      → arroba obligatoria
 *   [a-zA-Z0-9.\-]+        → dominio: letras, números, puntos y guiones
 *   \.                     → punto separador antes de la extensión
 *   [a-zA-Z]{2,}$          → extensión de al menos 2 letras (.com, .co, .org, .info…)
 */
export const REGEX_CORREO = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

/**
 * Reglas por nombre de campo.
 *   soloNumericos  → bloquea teclas y paste no numéricos.
 *   longitudExacta → valida longitud exacta en N dígitos.
 *   longitudMaxima → valida longitud máxima de N dígitos.
 *   soloPositivo   → bloquea signo negativo; min=0 en el input.
 *   formatoCorreo  → valida estructura usuario@dominio.ext
 */
export const REGLAS_INPUT = {
  numero_identificacion:    { soloNumericos: true },
  numero_doc_representante: { soloNumericos: true },
  telefono:                 { soloNumericos: true, longitudExacta: 10 },
  telefono_representante:   { soloNumericos: true, longitudExacta: 10 },
  codigo_ciiu:              { soloNumericos: true, longitudMaxima: 4 },
  codigo_ica:               { soloNumericos: true, longitudMaxima: 4 },
  ingresos_mensuales:       { soloNumericos: true, soloPositivo: true },
  otros_ingresos:           { soloNumericos: true, soloPositivo: true },
  egresos_mensuales:        { soloNumericos: true, soloPositivo: true },
  total_activos:            { soloNumericos: true, soloPositivo: true },
  total_pasivos:            { soloNumericos: true, soloPositivo: true },
  patrimonio:               { soloNumericos: true, soloPositivo: true },
  correo:                   { formatoCorreo: true },
  correo_representante:     { formatoCorreo: true },
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
    // Solo aplica blockNegativeKeyDown si soloNumericos no lo cubre ya
    if (!reglas.soloNumericos) props.onKeyDown = blockNegativeKeyDown;
    props.min = 0;
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
    if (reglas.formatoCorreo && !REGEX_CORREO.test(valor)) {
      errores[campo] = 'Ingrese un correo electrónico válido (ej: nombre@dominio.com)';
    }
  }
  return errores;
}
