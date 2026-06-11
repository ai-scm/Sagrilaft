/**
 * Catálogo de campos identificables en una solicitud de devolución.
 *
 * Espeja backend/domain/catalogo_correcciones.py — los IDs deben ser idénticos.
 * Agregar nuevos campos aquí (y en el backend) es la única acción necesaria
 * para extender el sistema a nuevos campos sin tocar componentes.
 *
 * Estructura:
 *   paso       — número de paso del formulario multipágina
 *   etiqueta   — nombre de la sección que ve el usuario del portal
 *   campos     — lista de { id, etiqueta } ordenada como aparece en el formulario
 */

export const CATALOGO_CORRECCIONES = [
  {
    paso: 2,
    etiqueta: 'Información básica',
    campos: [
      { id: 'tipo_contraparte',       etiqueta: 'Tipo de Contraparte' },
      { id: 'tipo_persona',           etiqueta: 'Tipo de Persona' },
      { id: 'tipo_solicitud',         etiqueta: 'Tipo de Solicitud' },
      { id: 'clasificacion_actividad',etiqueta: 'Clasificación de Actividad' },
      { id: 'razon_social',           etiqueta: 'Razón Social / Nombre' },
      { id: 'tipo_identificacion',    etiqueta: 'Tipo de Identificación' },
      { id: 'numero_identificacion',  etiqueta: 'Número de Identificación / NIT' },
      { id: 'digito_verificacion',    etiqueta: 'Dígito de Verificación' },
      { id: 'direccion',              etiqueta: 'Dirección' },
      { id: 'pais',                   etiqueta: 'País' },
      { id: 'departamento',           etiqueta: 'Departamento' },
      { id: 'ciudad',                 etiqueta: 'Ciudad' },
      { id: 'telefono',               etiqueta: 'Teléfono' },
      { id: 'fax',                    etiqueta: 'Fax' },
      { id: 'correo',                 etiqueta: 'Correo Electrónico' },
      { id: 'codigo_ica',             etiqueta: 'Código ICA' },
      { id: 'pagina_web',             etiqueta: 'Página Web' },
    ],
  },
  {
    paso: 3,
    etiqueta: 'Representante legal',
    campos: [
      { id: 'nombre_representante',       etiqueta: 'Nombre Completo' },
      { id: 'tipo_doc_representante',     etiqueta: 'Tipo de Documento' },
      { id: 'numero_doc_representante',   etiqueta: 'Número de Documento' },
      { id: 'fecha_expedicion',           etiqueta: 'Fecha de Expedición' },
      { id: 'ciudad_expedicion',          etiqueta: 'Ciudad de Expedición' },
      { id: 'nacionalidad',               etiqueta: 'Nacionalidad' },
      { id: 'fecha_nacimiento',           etiqueta: 'Fecha de Nacimiento' },
      { id: 'ciudad_nacimiento',          etiqueta: 'Ciudad de Nacimiento' },
      { id: 'profesion',                  etiqueta: 'Profesión' },
      { id: 'correo_representante',       etiqueta: 'Correo Electrónico' },
      { id: 'telefono_representante',     etiqueta: 'Teléfono' },
      { id: 'direccion_funciones',        etiqueta: 'Dirección donde desempeña funciones' },
      { id: 'pais_funciones',             etiqueta: 'País de funciones' },
      { id: 'departamento_funciones',     etiqueta: 'Departamento de funciones' },
      { id: 'ciudad_funciones',           etiqueta: 'Ciudad de funciones' },
      { id: 'ciudad_residencia',          etiqueta: 'Ciudad de Residencia (Persona Natural)' },
      { id: 'direccion_residencia',       etiqueta: 'Dirección de Residencia (Persona Natural)' },
    ],
  },
  {
    paso: 4,
    etiqueta: 'Junta, accionistas y beneficiarios',
    campos: [
      { id: 'junta_directiva',   etiqueta: 'Miembros de Junta Directiva' },
      { id: 'accionistas',       etiqueta: 'Accionistas' },
      { id: 'beneficiario_final',etiqueta: 'Beneficiarios Finales' },
    ],
  },
  {
    paso: 5,
    etiqueta: 'Información financiera',
    campos: [
      { id: 'actividad_economica',  etiqueta: 'Actividad Económica' },
      { id: 'codigo_ciiu',          etiqueta: 'Código CIIU' },
      { id: 'ingresos_mensuales',   etiqueta: 'Ingresos Mensuales' },
      { id: 'otros_ingresos',       etiqueta: 'Otros Ingresos' },
      { id: 'egresos_mensuales',    etiqueta: 'Egresos Mensuales' },
      { id: 'total_activos',        etiqueta: 'Total Activos' },
      { id: 'total_pasivos',        etiqueta: 'Total Pasivos' },
      { id: 'patrimonio',           etiqueta: 'Patrimonio' },
    ],
  },
  {
    paso: 6,
    etiqueta: 'Operaciones y referencias',
    campos: [
      { id: 'realiza_operaciones_moneda_extranjera', etiqueta: '¿Realiza Operaciones en Moneda Extranjera?' },
      { id: 'paises_operaciones',    etiqueta: 'Países de Operaciones' },
      { id: 'tipos_transaccion',     etiqueta: 'Tipos de Transacción' },
      { id: 'referencias_comerciales', etiqueta: 'Referencias Comerciales' },
      { id: 'referencias_bancarias', etiqueta: 'Referencias Bancarias' },
    ],
  },
  {
    paso: 7,
    etiqueta: 'Clasificación y contactos',
    campos: [
      { id: 'actividad_clasificacion',      etiqueta: 'Actividad / Clasificación' },
      { id: 'sector',                       etiqueta: 'Sector Económico' },
      { id: 'superintendencia',             etiqueta: 'Superintendencia' },
      { id: 'contacto_ordenes_nombre',      etiqueta: 'Contacto Órdenes — Nombre' },
      { id: 'contacto_ordenes_cargo',       etiqueta: 'Contacto Órdenes — Cargo' },
      { id: 'contacto_ordenes_telefono',    etiqueta: 'Contacto Órdenes — Teléfono' },
      { id: 'contacto_ordenes_correo',      etiqueta: 'Contacto Órdenes — Correo' },
      { id: 'contacto_pagos_nombre',        etiqueta: 'Contacto Pagos — Nombre' },
      { id: 'contacto_pagos_cargo',         etiqueta: 'Contacto Pagos — Cargo' },
      { id: 'contacto_pagos_telefono',      etiqueta: 'Contacto Pagos — Teléfono' },
      { id: 'contacto_pagos_correo',        etiqueta: 'Contacto Pagos — Correo' },
      { id: 'informacion_bancaria_pagos',   etiqueta: 'Información Bancaria de Pagos' },
    ],
  },
  {
    paso: 8,
    etiqueta: 'Declaraciones y firma',
    campos: [
      { id: 'origen_fondos', etiqueta: 'Origen de Fondos' },
      { id: 'dia_firma',     etiqueta: 'Día de Firma' },
      { id: 'mes_firma',     etiqueta: 'Mes de Firma' },
      { id: 'year_firma',    etiqueta: 'Año de Firma' },
      { id: 'ciudad_firma',  etiqueta: 'Ciudad de Firma' },
    ],
  },
];

/**
 * Mapa plano id → etiqueta para consultas rápidas.
 * Construido una sola vez al cargar el módulo.
 */
export const ETIQUETA_POR_CAMPO = Object.fromEntries(
  CATALOGO_CORRECCIONES.flatMap(grupo => grupo.campos.map(campo => [campo.id, campo.etiqueta])),
);

/**
 * Mapa id → número de paso para navegación directa desde la corrección.
 */
export const PASO_POR_CAMPO = Object.fromEntries(
  CATALOGO_CORRECCIONES.flatMap(grupo => grupo.campos.map(campo => [campo.id, grupo.paso])),
);
