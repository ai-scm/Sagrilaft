/**
 * Configuración declarativa del formulario SAGRILAFT.
 * Centraliza constantes y metadatos para que los pasos
 * no tengan magic strings ni números mágicos dispersos.
 */

export const TOTAL_STEPS = 7;

/**
 * Cargos válidos para la Junta Directiva y Representantes.
 * Fuente única de verdad — agregar nuevas opciones aquí sin tocar el componente.
 */
export const CARGOS_JUNTA_DIRECTIVA = [
  'Presidente',
  'Gerente General / Representante Legal',
  'Gerente Suplente',
  'Segundo Suplente del Gerente',
  'Junta Directiva Principal Primer Renglón',
  'Junta Directiva Principal Segundo Renglón',
  'Junta Directiva Principal Tercer Renglón',
];

/**
 * Documentos adjuntos requeridos.
 * soloJuridica: true → se omite para Persona Natural.
 */
export const DOCUMENTOS_CONFIG = [
  { label: 'Cédula del Representante Legal',                   tipoDoc: 'cedula_representante',   accepted: '.pdf,.jpg,.jpeg,.png', soloJuridica: true  },
  { label: 'Certificado de Existencia y Representación Legal', tipoDoc: 'certificado_existencia', accepted: '.pdf', hint: 'No mayor a 30 días', soloJuridica: true  },
  { label: 'Estados Financieros',                              tipoDoc: 'estados_financieros',    accepted: '.pdf', soloJuridica: true  },
  { label: 'Declaración de Renta',                             tipoDoc: 'declaracion_renta',      accepted: '.pdf', soloJuridica: true  },
  { label: 'RUT (Registro Único Tributario)',                  tipoDoc: 'rut',                    accepted: '.pdf', hint: 'Debe ser del año en curso', soloJuridica: false },
  { label: 'Referencias Bancarias',                            tipoDoc: 'referencias_bancarias',  accepted: '.pdf', soloJuridica: false },
];

/**
 * Campos obligatorios por paso.
 * Fuente única de verdad para validación en useFormulario.
 */
export const CAMPOS_REQUERIDOS = {
  1: [],
  2: ['tipo_contraparte', 'tipo_persona', 'tipo_solicitud', 'razon_social', 'tipo_identificacion', 'numero_identificacion', 'direccion', 'departamento', 'ciudad', 'telefono', 'correo', 'codigo_ica'],
  3: ['nombre_representante', 'tipo_doc_representante', 'numero_doc_representante', 'fecha_expedicion', 'ciudad_expedicion', 'nacionalidad', 'fecha_nacimiento', 'ciudad_nacimiento', 'profesion', 'correo_representante', 'telefono_representante', 'direccion_funciones', 'ciudad_funciones'],
  4: [],
  5: ['actividad_economica', 'codigo_ciiu', 'ingresos_mensuales', 'egresos_mensuales', 'total_activos', 'total_pasivos', 'patrimonio'],
  6: [],
  7: ['origen_fondos', 'nombre_firma', 'fecha_firma', 'ciudad_firma'],
};
