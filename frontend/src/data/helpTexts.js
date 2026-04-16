/**
 * Textos de ayuda para cada campo del formulario SAGRILAFT.
 * Cada campo tiene un título y una descripción que se muestra en el panel lateral.
 */
const helpTexts = {
  // Clasificación
  tipo_contraparte: {
    titulo: "Tipo de Contraparte",
    descripcion: "Seleccione si la contraparte actúa como proveedor (le vende a la empresa) o como cliente (le compra a la empresa).",
    ejemplo: "Si la empresa contrata servicios de un tercero, este sería un Proveedor."
  },
  tipo_persona: {
    titulo: "Tipo de Persona",
    descripcion: "Persona Jurídica: empresa o sociedad constituida legalmente. Persona Natural: individuo que actúa en nombre propio.",
    ejemplo: "Una S.A.S. o Ltda. es Persona Jurídica. Un freelancer es Persona Natural."
  },
  tipo_solicitud: {
    titulo: "Tipo de Solicitud",
    descripcion: "Vinculación: primera vez que se registra esta contraparte. Actualización: modificación de datos de una contraparte ya registrada.",
  },
  clasificacion_actividad: {
    titulo: "Clasificación de Actividad",
    descripcion: `
Identifique el rol principal de la contraparte según su actividad económica:

(C) Comercializador: Vende productos al cliente final.

(D) Distribuidor: Redistribuye productos bajo licencia o contrato del fabricante.

(R) Representante: Actúa legalmente en nombre de otra empresa o firma extranjera.

(F) Fabricante: Produce o transforma el bien. 

(I) Importador: Introduce productos al país. Puede identificarse en el RUT (casilla de usuario aduanero).

Nota: Si la contraparte tiene varias actividades, seleccione la principal,
es decir, la que genera mayores ingresos o la registrada como principal en Cámara de Comercio o RUT.
La clasificación se relaciona con el CIIU
`,
    ejemplo: "Seleccione 'Fabricante (F)' si la empresa produce los bienes que le vende."
  },

  // Info Básica
  razon_social: {
    titulo: "Nombre o Razón Social",
    descripcion: "Nombre completo de la empresa tal como aparece en el certificado de cámara de comercio o RUT. Para persona natural, nombres y apellidos completos.",
    ejemplo: "HIGHTECH SOFTWARE CONTABLE S.A.S."
  },
  tipo_identificacion: {
    titulo: "Tipo de Identificación",
    descripcion: "NIT para personas jurídicas colombianas, Cédula de Ciudadanía para personas naturales colombianas, Cédula de Extranjería o Pasaporte para extranjeros.",
  },
  numero_identificacion: {
    titulo: "Número de Identificación",
    descripcion: "Ingrese el número sin puntos ni guiones. El dígito de verificación (DV) se ingresa en el campo separado a la derecha.",
    ejemplo: "Para NIT: 900718336. Para CC: 1020345678"
  },
  digito_verificacion: {
    titulo: "Dígito de Verificación (DV)",
    descripcion: "Este dígito se encuentra en el RUT en la casilla 6 llamada DV. Solo aplica para NIT.",
    ejemplo: "5"
  },
  direccion: {
    titulo: "Dirección",
    descripcion: "Dirección principal de la empresa o domicilio de la persona natural. Incluya nomenclatura completa.",
    ejemplo: "Calle 100 # 19A - 30, Oficina 501"
  },
  pais: {
    titulo: "País",
    descripcion: "País donde se encuentra la sede principal de la contraparte.",
  },
  departamento: {
    titulo: "Departamento",
    descripcion: "Departamento colombiano donde opera la contraparte.",
  },
  ciudad: {
    titulo: "Ciudad",
    descripcion: "Ciudad de la sede principal.",
  },
  telefono: {
    titulo: "Teléfono",
    descripcion: "Número telefónico principal.",
    ejemplo: "310 2345678"
  },
  correo: {
    titulo: "Correo Electrónico",
    descripcion: "Dirección de correo electrónico corporativo/oficial para comunicaciones oficiales.",
    ejemplo: "contacto@empresa.com o correoprincipal@dominio.com"
  },
  codigo_ica: {
    titulo: "Código Actividad ICA",
    descripcion: "Código de la actividad económica para el Impuesto de Industria y Comercio. Puede consultarse en el RUT.",
  },
  fax: {
    titulo: "Fax",
    descripcion: "Número de fax de la empresa. Si la empresa no cuenta con fax, escribe NA.",
    ejemplo: "Si no aplica, escribe NA"
  },
  pagina_web: {
    titulo: "Página Web",
    descripcion: "Dirección web oficial de la empresa. Si la empresa no tiene sitio web, escribe NA.",
    ejemplo: "https://www.empresa.com — Si no aplica, escribe NA"
  },

  // Representante Legal
  nombre_representante: {
    titulo: "Nombres y Apellidos del Representante Legal",
    descripcion: "Nombre completo tal como aparece en los certificados anteriores. Para persona natural, ingrese su propio nombre completo.",
  },
  tipo_doc_representante: {
    titulo: "Tipo de Documento",
    descripcion: "Tipo de documento de identidad del representante legal.",
  },
  numero_doc_representante: {
    titulo: "Número de Identificación",
    descripcion: "Número de documento del representante legal sin puntos ni espacios.",
  },
  fecha_expedicion: {
    titulo: "Fecha de Expedición",
    descripcion: "Fecha en que fue expedido el documento de identidad del representante legal. Se encuentra en el documento principal de identificacion",
  },
  ciudad_expedicion: {
    titulo: "Ciudad de Expedición",
    descripcion: "Ciudad donde fue expedido el documento de identidad.",
  },
  nacionalidad: {
    titulo: "Nacionalidad",
    descripcion: "País de nacionalidad del representante legal.",
  },
  fecha_nacimiento: {
    titulo: "Fecha de Nacimiento",
    descripcion: "Fecha de nacimiento del representante legal.",
  },
  ciudad_nacimiento: {
    titulo: "Ciudad de Nacimiento",
    descripcion: "Ciudad de nacimiento del representante legal.",
  },
  profesion: {
    titulo: "Profesión",
    descripcion: "Profesión o título profesional del representante legal.",
    ejemplo: "Ingeniero de Sistemas, Abogado, Administrador de Empresas"
  },
  correo_representante: {
    titulo: "Correo Electrónico del Representante",
    descripcion: "Correo electrónico directo del representante legal.",
  },
  telefono_representante: {
    titulo: "Teléfono del Representante",
    descripcion: "Número de contacto directo del representante legal - CELULAR 10 digitos.",
  },
  direccion_funciones: {
    titulo: "Dirección donde Ejerce Funciones",
    descripcion: "Dirección del lugar donde el representante legal ejerce sus funciones.",
  },
  ciudad_funciones: {
    titulo: "Ciudad donde Ejerce Funciones",
    descripcion: "Ciudad donde el representante legal desarrolla habitualmente sus actividades.",
  },
  departamento_funciones: {
    titulo: "Departamento (Funciones)",
    descripcion: "Departamento donde el representante legal ejerce sus funciones. Selecciónelo para filtrar las ciudades disponibles.",
  },
  pais_funciones: {
    titulo: "País (Funciones)",
    descripcion: "País donde el representante legal ejerce sus funciones.",
  },
  direccion_residencia: {
    titulo: "Dirección de Residencia",
    descripcion: "Dirección de residencia actual de la persona natural.",
    ejemplo: "Carrera 15 # 80 - 22, Apto 301"
  },
  ciudad_residencia: {
    titulo: "Ciudad de Residencia",
    descripcion: "Ciudad donde reside actualmente la persona natural.",
  },

  // Financiera
  actividad_economica: {
    titulo: "Actividad Económica Principal",
    descripcion: "Descripción de la actividad económica principal de la contraparte según el registro mercantil. (Se valida con base al codigo CIIU)",
    ejemplo: "Desarrollo de aplicaciones de software"
  },
  codigo_ciiu: {
    titulo: "Código CIIU",
    descripcion: "Código Internacional Industrial Uniforme de la actividad económica principal. Se encuentra en el RUT. (Campo en el RUT: 46. Código). (Campo en el certificado de cámara de comercio: Actividad económica principal)",
    ejemplo: "6201 - Actividades de desarrollo de sistemas informáticos"
  },
  ingresos_mensuales: {
    titulo: "Ingresos Mensuales",
    descripcion: "Total de ingresos mensuales en pesos colombianos (COP). Debe coincidir con los estados financieros adjuntos.",
  },
  egresos_mensuales: {
    titulo: "Egresos Mensuales",
    descripcion: "Total de gastos y costos mensuales en pesos colombianos (COP).",
  },
  total_activos: {
    titulo: "Total Activos",
    descripcion: "Valor total de activos según el último estado financiero. Se validará contra los estados financieros adjuntos.",
  },
  total_pasivos: {
    titulo: "Total Pasivos",
    descripcion: "Valor total de pasivos según el último estado financiero.",
  },
  patrimonio: {
    titulo: "Patrimonio",
    descripcion: "Patrimonio neto (Activos - Pasivos). Este valor se verificará contra los estados financieros adjuntos.",
  },

  // Clasificación tributaria
  actividad_clasificacion: { titulo: "Actividad", descripcion: "Actividad principal de la empresa." },
  actividad_especifica: { titulo: "Actividad Específica", descripcion: "Especifique la actividad de la empresa." },
  sector: {
    titulo: "Sector",
    descripcion: "Sector económico al que pertenece la empresa. Público: entidades del Estado o con mayoría de capital público. Privado: empresas de capital exclusivamente privado. Mixto: empresas con participación tanto pública como privada.",
    ejemplo: "Una sociedad de economía mixta selecciona 'Mixto'. Una S.A.S. de capital privado selecciona 'Privado'."
  },
  superintendencia: { titulo: "Vigilado por la Superintendencia de", descripcion: "Superintendencia que vigila a la empresa." },
  responsabilidades_renta: { 
    titulo: "Responsabilidades Impuesto sobre la Renta", 
    descripcion: "Indica la clasificación de la empresa frente al impuesto sobre la renta: Declarante (obligado a presentar declaración), No declarante (exonerado por ley) o Declarante Regimen Especial (perteneciente al régimen tributario especial para entidades sin ánimo de lucro, cooperativas, etc.)." 
  },
  autorretenedor: { titulo: "Autorretenedor", descripcion: "Indica si la empresa es autorretenedora." },
  responsabilidades_iva: { 
    titulo: "Responsabilidades en el IVA", 
    descripcion: "Indica si la empresa es Responsable (antes régimen común) o No responsable de facturar y recaudar IVA por la venta de bienes o servicios." 
  },
  regimen_iva: { 
    titulo: "Régimen IVA", 
    descripcion: "Seleccione el régimen de impuesto sobre las ventas al que pertenece: Régimen común, Régimen simplificado o Ningún régimen." 
  },
  gran_contribuyente: { titulo: "¿Es Gran Contribuyente?", descripcion: "Indica si la empresa es catalogada como gran contribuyente." },
  entidad_sin_animo_lucro: { titulo: "Entidad sin Ánimo de Lucro", descripcion: "Indica si es una entidad sin ánimo de lucro." },
  retencion_ica: { titulo: "Retención de Industria y Comercio", descripcion: "Indique 'Sí' o 'No' aplica retención de ICA." },
  impuesto_ica: { titulo: "Impuesto de Industria y Comercio", descripcion: "Indique 'Sí' o 'No' aplica el ICA a la empresa." },
  entidad_oficial: { titulo: "Entidad Oficial", descripcion: "Indica si es una entidad del Estado." },
  exento_retencion_fuente: { titulo: "Exento de Retención en la Fuente", descripcion: "Indica si la empresa está exenta de retención en la fuente." },

  // Contactos
  contacto_ordenes_nombre: { titulo: "Nombre (Órdenes de Compra)", descripcion: "Persona autorizada para recibir órdenes de compra y de servicio." },
  contacto_ordenes_cargo: { titulo: "Cargo (Órdenes de Compra)", descripcion: "Cargo de la persona para órdenes de compra." },
  contacto_ordenes_telefono: { titulo: "Teléfono (Órdenes de Compra)", descripcion: "Teléfono de contacto para órdenes de compra." },
  contacto_ordenes_correo: { titulo: "Correo (Órdenes de Compra)", descripcion: "Correo electrónico para órdenes de compra." },
  contacto_pagos_nombre: { titulo: "Nombre (Reportes de Pago)", descripcion: "Persona autorizada para recibir reportes y comunicaciones de pago." },
  contacto_pagos_cargo: { titulo: "Cargo (Reportes de Pago)", descripcion: "Cargo de la persona para reportes de pago." },
  contacto_pagos_telefono: { titulo: "Teléfono (Reportes de Pago)", descripcion: "Teléfono de contacto para reportes de pago." },
  contacto_pagos_correo: { titulo: "Correo (Reportes de Pago)", descripcion: "Correo electrónico para reportes de pago." },

  // Documentos
  doc_cedula_representante: {
    titulo: "Cédula del Representante Legal",
    descripcion: "Fotocopia legible de ambos lados de la cédula de ciudadanía del representante legal. Formato PDF, JPG o PNG.",
  },
  doc_rut: {
    titulo: "Registro Único Tributario (RUT)",
    descripcion: "Copia del RUT actualizado. DEBE ser del año en curso. Se verificará que nombre, NIT y actividades económicas coincidan con el formulario.",
  },
  doc_certificado_existencia: {
    titulo: "Certificado de Existencia y Representación Legal",
    descripcion: "Certificado expedido por la Cámara de Comercio. NO debe tener más de 30 días de antigüedad. Se verificará razón social, NIT y representante legal.",
  },
  doc_estados_financieros: {
    titulo: "Estados Financieros",
    descripcion: "Estados financieros del último cierre fiscal. Las cifras reportadas se contrastarán con la información financiera del formulario (activos, pasivos, patrimonio).",
  },
  doc_declaracion_renta: {
    titulo: "Declaración de Renta",
    descripcion: "Copia de la declaración de renta del año inmediatamente anterior.",
  },
  doc_referencias_bancarias: {
    titulo: "Referencias Bancarias",
    descripcion: "Certificación bancaria vigente que acredite existencia de cuenta. No debe tener más de 30 días de antigüedad.",
  },
  realiza_operaciones_moneda_extranjera: {
    titulo: "¿Realiza Operaciones en Moneda Extranjera?",
    descripcion: "Indique si la empresa realiza transacciones en divisas distintas al peso colombiano (importaciones, exportaciones, inversiones en el exterior, etc.).",
    ejemplo: "Seleccione 'Sí' si tiene pagos o cobros en dólares, euros u otra divisa.",
  },
};

export default helpTexts;
