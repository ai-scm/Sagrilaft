/**
 * Reglas de validación de input centralizadas.
 *
 * Fuente única de verdad para restricciones de campos numéricos.
 * Consumido por FormField (bloqueo en tiempo real) y useFormValidacion (errores al avanzar).
 *
 * Para agregar reglas a un campo nuevo, solo editar REGLAS_INPUT.
 */

import {
  REGEX_CORREO,
  REGEX_CHAR_TEXTO,
  REGEX_CHAR_ALFANUMERICO_ESTRICTO,
  REGEX_CHAR_ALFANUMERICO,
} from '@shared/utils/constantes';

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

/**
 * Bloquea caracteres inválidos en campos de porcentaje (% Participación, % Control).
 * type="number" ya rechaza la mayoría de letras, pero permite '-', '+', 'e', 'E'
 * por notación científica — este handler los elimina.
 */
export const onPorcentajeKeyDown = (e) => {
  if (e.ctrlKey || e.metaKey) return;
  if (['-', '+', 'e', 'E'].includes(e.key)) e.preventDefault();
};

/** Bloquea pegado de contenido no numérico en campos de porcentaje. */
export const onPorcentajePaste = (e) => {
  if (!/^\d*\.?\d*$/.test(e.clipboardData.getData('text'))) {
    e.preventDefault();
  }
};

/**
 * Reglas por nombre de campo.
 *   soloNumericos  → bloquea teclas y paste no numéricos.
 *   longitudExacta → valida longitud exacta en N dígitos.
 *   longitudMaxima → valida longitud máxima de N dígitos.
 *   soloPositivo   → bloquea signo negativo; min=0 en el input.
 *   formatoCorreo  → valida estructura usuario@dominio.ext
 */
export const REGLAS_INPUT = {
  digito_verificacion: { soloNumericos: true },
  // numero_doc_representante usa getIdPropsByTipoDocumento() dinámicamente en PasoRepresentante
  // (numérico para CC/CE/NIT, alfanumérico para Pasaporte/otros) — no va aquí.
  telefono: { soloNumericos: true },
  telefono_representante: { soloNumericos: true },
  codigo_ciiu: { soloNumericos: true, longitudMaxima: 4 },
  codigo_ica: { soloNumericos: true, longitudMaxima: 4 },
  ingresos_mensuales: { soloNumericos: true, soloPositivo: true },
  otros_ingresos: { soloNumericos: true, soloPositivo: true },
  egresos_mensuales: { soloNumericos: true, soloPositivo: true },
  total_activos: { soloNumericos: true, soloPositivo: true },
  total_pasivos: { soloNumericos: true, soloPositivo: true },
  patrimonio: { soloNumericos: true, soloPositivo: true },
  correo: { formatoCorreo: true },
  correo_representante: { formatoCorreo: true },
  contacto_ordenes_telefono: { soloNumericos: true },
  contacto_pagos_telefono: { soloNumericos: true },
  contacto_ordenes_correo: { formatoCorreo: true },
  contacto_pagos_correo: { formatoCorreo: true },
  dia_firma: { soloNumericos: true, valorMinimo: 1, valorMaximo: 31 },
  mes_firma: { soloNumericos: true, valorMinimo: 1, valorMaximo: 12 },
  year_firma: { soloNumericos: true, valorMinimo: 2026, valorMaximo: 2028 },
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
    props.onPaste = onlyNumericPaste;
    props.inputMode = 'numeric';
  }
  if (reglas.soloPositivo) {
    if (!reglas.soloNumericos) props.onKeyDown = onPorcentajeKeyDown;
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
 * Retorna las props onKeyDown, onPaste e inputMode para un campo de identificación
 * dependiendo de su tipo de documento seleccionado.
 */
export function getIdPropsByTipoDocumento(tipoDoc) {
  if (['CC', 'CE', 'NIT'].includes(tipoDoc)) {
    return {
      onKeyDown: onlyNumericKeyDown,
      onPaste: onlyNumericPaste,
      inputMode: 'numeric',
    };
  }
  return {
    onKeyDown: onlyAlphanumericStrictKeyDown,
    onPaste: onlyAlphanumericStrictPaste,
    inputMode: 'text',
  };
}

/**
 * Retorna las propiedades dinámicas (deshabilitado, lectura, obligatoriedad, etc.)
 * para el campo DV dependiendo del Tipo de Identificación.
 */
export function getDvProps(tipo_identificacion) {
  const isNIT = tipo_identificacion === 'NIT';
  return {
    label: isNIT ? 'DV' : 'DV', // Si no es NIT, el valor forzado será 'NA'
    required: isNIT,
    disabled: !isNIT, // Previene interacción
    readOnly: !isNIT, // Doble validación para inmutabilidad
    maxLength: isNIT ? 1 : 2,
  };
}

/**
 * Determina el valor del DV cuando cambia el Tipo de Identificación.
 */
export function calcularValorDv(nuevoTipoIdentificacion, valorActual) {
  return nuevoTipoIdentificacion === 'NIT' ? (valorActual === 'NA' ? '' : valorActual) : 'NA';
}


/**
 * Limpia el valor ingresado asegurando que cumpla el patrón del tipo de documento.
 * Útil para interceptar en onChange y evitar autocompletados inválidos.
 */
export function sanitizeIdValue(value, tipoDoc) {
  if (!value) return '';
  // CC, CE, NIT -> Solo dígitos
  if (['CC', 'CE', 'NIT'].includes(tipoDoc)) {
    return value.replace(/\D/g, '');
  }
  // Otros -> Alfanumérico sin caracteres especiales
  return value.replace(/[^a-zA-Z0-9]/g, '');
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

    if (campo === 'digito_verificacion') {
      const isNIT = formData.tipo_identificacion === 'NIT';
      const upperVal = valor.toUpperCase();
      if (isNIT) {
        if (!/^\d$/.test(valor)) {
          errores[campo] = 'Debe ser un único dígito numérico (0-9)';
        }
      } else {
        if (upperVal !== 'NA') {
          errores[campo] = 'Debe ser "NA" para este tipo de identificación';
        }
      }
      continue;
    }

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
    if (reglas.valorMinimo && parseFloat(valor) < reglas.valorMinimo) {
      errores[campo] = `El valor no puede ser menor a ${reglas.valorMinimo}`;
    }
    if (reglas.valorMaximo && parseFloat(valor) > reglas.valorMaximo) {
      errores[campo] = `El valor no puede ser mayor a ${reglas.valorMaximo}`;
    }
    if (reglas.formatoCorreo && !REGEX_CORREO.test(valor)) {
      errores[campo] = 'Ingrese un correo electrónico válido (ej: nombre@dominio.com)';
    }
  }
  return errores;
}
