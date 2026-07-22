/**
 * Configuración declarativa del formulario SAGRILAFT.
 * Centraliza constantes y metadatos para que los pasos
 * no tengan magic strings ni números mágicos dispersos.
 */

export const TOTAL_STEPS = 8;

/**
 * Devuelve los números de paso visibles para el formData actual.
 * El Paso 4 (Junta / Accionistas / Beneficiarios) solo aplica a Persona Jurídica.
 */
export function calcularPasosVisibles(formData = {}) {
  const todos = Array.from({ length: TOTAL_STEPS }, (_, i) => i + 1);
  if (formData.tipo_persona === 'natural') {
    return todos.filter(p => p !== 4);
  }
  return todos;
}

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
 * Todos se muestran siempre, independientemente del tipo de persona.
 */
export const DOCUMENTOS_CONFIG = [
  { label: 'Cédula del Representante Legal',                   tipoDoc: 'cedula_representante',   accepted: '.pdf,.jpg,.jpeg,.png' },
  { label: 'Certificado de Existencia y Representación Legal', tipoDoc: 'certificado_existencia', accepted: '.pdf', hint: 'No mayor a 30 días' },
  { label: 'Estados Financieros',                              tipoDoc: 'estados_financieros',    accepted: '.pdf' },
  { label: 'Declaración de Renta',                             tipoDoc: 'declaracion_renta',      accepted: '.pdf' },
  { label: 'RUT (Registro Único Tributario)',                  tipoDoc: 'rut',                    accepted: '.pdf', hint: 'Debe ser del año en curso' },
  { label: 'Referencias Bancarias',                            tipoDoc: 'referencias_bancarias',  accepted: '.pdf' },
];

/**
 * Campos exclusivos de Persona Natural.
 * Fuente única de verdad — espeja _CAMPOS_PERSONA_NATURAL del backend.
 */
export const CAMPOS_PERSONA_NATURAL = ['ciudad_residencia', 'direccion_residencia'];

/**
 * Campos de clasificación tributaria exclusivos de Persona Jurídica.
 * Persona Natural conserva contacto e información bancaria, pero no diligencia
 * la clasificación de empresa ni régimen tributario.
 */
export const CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA = [
  'actividad_clasificacion',
  'actividad_especifica',
  'sector',
  'superintendencia',
  'responsabilidades_renta',
  'autorretenedor',
  'responsabilidades_iva',
  'regimen_iva',
  'gran_contribuyente',
  'entidad_sin_animo_lucro',
  'retencion_ica',
  'impuesto_ica',
  'entidad_oficial',
  'exento_retencion_fuente',
];

/**
 * Mensajes de validación para los campos dependientes de moneda extranjera (Paso 6).
 * Fuente única de verdad — espeja los mensajes del backend (validacion_envio.py).
 */
const MENSAJES_VALIDACION_MONEDA_EXTRANJERA = {
  paises_operaciones:      'El campo "Países en los que realiza operaciones" es obligatorio',
  tipos_transaccion:       'Debe seleccionar al menos un tipo de transacción',
  tipos_transaccion_otros: 'El campo "¿Cuáles?" es obligatorio cuando selecciona "Otras"',
};

/**
 * Campos obligatorios condicionalmente por paso, según el tipo de persona.
 * Cada entrada es una lista de { condicion, campos } — si condicion(formData) es true,
 * esos campos se validan como obligatorios. Agregar nuevos casos aquí sin tocar validarPaso.
 */
export const CAMPOS_CONDICIONALES = {
  2: [
    {
      condicion: (fd) => fd.tipo_identificacion === 'NIT',
      campos: ['digito_verificacion'],
      mensajes: {
        digito_verificacion: 'Dígito de Verificación (DV) es obligatorio para el NIT',
      },
    },
  ],
  3: [
    {
      condicion: (fd) => fd.tipo_persona === 'natural',
      campos: CAMPOS_PERSONA_NATURAL,
      mensajes: {
        ciudad_residencia: 'Ciudad de Residencia es obligatoria',
        direccion_residencia: 'Dirección de Residencia es obligatoria',
      },
    },
  ],
  6: [
    {
      condicion: (fd) => fd.realiza_operaciones_moneda_extranjera === true,
      campos: ['paises_operaciones', 'tipos_transaccion'],
      mensajes: MENSAJES_VALIDACION_MONEDA_EXTRANJERA,
    },
    {
      condicion: (fd) =>
        fd.realiza_operaciones_moneda_extranjera === true &&
        Array.isArray(fd.tipos_transaccion) &&
        fd.tipos_transaccion.includes('otras'),
      campos: ['tipos_transaccion_otros'],
      mensajes: MENSAJES_VALIDACION_MONEDA_EXTRANJERA,
    },
  ],
  7: [
    {
      condicion: (fd) => fd.tipo_persona === 'juridica',
      campos: CAMPOS_CLASIFICACION_TRIBUTARIA_EMPRESA,
    },
  ],
};

/**
 * Campos obligatorios por paso.
 * Fuente única de verdad para validación en useFormulario.
 */
export const CAMPOS_REQUERIDOS = {
  1: [],
  2: ['tipo_contraparte', 'tipo_persona', 'tipo_solicitud', 'clasificacion_actividad', 'razon_social', 'tipo_identificacion', 'numero_identificacion', 'direccion', 'pais', 'departamento', 'ciudad', 'telefono', 'fax', 'correo', 'codigo_ica', 'pagina_web'],
  3: ['nombre_representante', 'tipo_doc_representante', 'numero_doc_representante', 'fecha_expedicion', 'ciudad_expedicion', 'nacionalidad', 'fecha_nacimiento', 'ciudad_nacimiento', 'profesion', 'correo_representante', 'telefono_representante', 'direccion_funciones', 'pais_funciones', 'departamento_funciones', 'ciudad_funciones'],
  4: [],
  5: ['moneda_declaracion', 'moneda_declaracion_otra', 'actividad_economica', 'codigo_ciiu', 'ingresos_mensuales', 'egresos_mensuales', 'total_activos', 'total_pasivos', 'patrimonio'],
  6: ['realiza_operaciones_moneda_extranjera'],
  7: [
    'contacto_ordenes_nombre', 'contacto_ordenes_cargo', 'contacto_ordenes_telefono', 'contacto_ordenes_correo',
    'contacto_pagos_nombre',   'contacto_pagos_cargo',   'contacto_pagos_telefono',   'contacto_pagos_correo',
  ],
  8: ['origen_fondos', 'dia_firma', 'mes_firma', 'year_firma', 'ciudad_firma'],
};
