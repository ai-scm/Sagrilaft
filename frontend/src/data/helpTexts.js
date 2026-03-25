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
    descripcion: "Ingrese el número sin puntos ni guiones. Si es NIT, incluya el dígito de verificación.",
    ejemplo: "Para NIT: 9007183367. Para CC: 1020345678"
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
    descripcion: "Dirección de correo electrónico corporativo para comunicaciones oficiales.",
    ejemplo: "contacto@empresa.com"
  },
  codigo_ica: {
    titulo: "Código Actividad ICA",
    descripcion: "Código de la actividad económica para el Impuesto de Industria y Comercio. Puede consultarse en el RUT.",
  },
  pagina_web: {
    titulo: "Página Web",
    descripcion: "URL del sitio web de la contraparte (opcional).",
    ejemplo: "https://www.empresa.com"
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
    descripcion: "Fecha en que fue expedido el documento de identidad del representante legal.",
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
    descripcion: "Número de contacto directo del representante legal.",
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
  departamento_expedicion: {
    titulo: "Departamento de Expedición",
    descripcion: "Departamento colombiano donde fue expedido el documento de identidad. Selecciónelo para filtrar las ciudades disponibles.",
  },
  pais_expedicion: {
    titulo: "País de Expedición",
    descripcion: "País donde fue expedido el documento de identidad del representante legal.",
  },
  departamento_nacimiento: {
    titulo: "Departamento de Nacimiento",
    descripcion: "Departamento colombiano de nacimiento del representante legal. Selecciónelo para filtrar las ciudades disponibles.",
  },
  pais_nacimiento: {
    titulo: "País de Nacimiento",
    descripcion: "País de nacimiento del representante legal.",
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
    descripcion: "Descripción de la actividad económica principal de la contraparte según el registro mercantil.",
    ejemplo: "Desarrollo de aplicaciones de software"
  },
  codigo_ciiu: {
    titulo: "Código CIIU",
    descripcion: "Código Internacional Industrial Uniforme de la actividad económica principal. Se encuentra en el RUT.",
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

  // Contactos
  contacto_ordenes_nombre: {
    titulo: "Contacto para Órdenes de Compra",
    descripcion: "Persona autorizada para recibir órdenes de compra y de servicio.",
  },
  contacto_pagos_nombre: {
    titulo: "Contacto para Pagos",
    descripcion: "Persona autorizada para recibir reportes y comunicaciones de pago.",
  },

  // Info Bancaria
  entidad_bancaria: {
    titulo: "Entidad Bancaria",
    descripcion: "Nombre del banco donde tiene la cuenta para recibir pagos.",
  },
  tipo_cuenta: {
    titulo: "Tipo de Cuenta",
    descripcion: "Tipo de cuenta bancaria (Ahorros o Corriente).",
  },
  numero_cuenta: {
    titulo: "Número de Cuenta",
    descripcion: "Número completo de la cuenta bancaria para pagos.",
  },

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
};

export default helpTexts;
