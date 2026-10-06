/**
 * networkMocks.js
 * Interceptores Playwright para simular todos los endpoints que usa el frontend.
 * La respuesta del login/token sigue la estructura plana que espera _adaptarRespuestaServidor.
 */

/** Datos mínimos de una Persona Jurídica completamente diligenciada */
export const MOCK_DATA_JURIDICA = {
  tipo_contraparte: 'proveedor',
  tipo_persona: 'juridica',
  tipo_solicitud: 'vinculacion',
  clasificacion_actividad: 'comercial',
  razon_social: 'Empresa Mock SAS',
  tipo_identificacion: 'nit',
  numero_identificacion: '900123456',
  digito_verificacion: '1',
  direccion: 'Calle Falsa 123',
  pais: 'CO',
  departamento: '11',
  ciudad: '11001',
  telefono: '3001234567',
  fax: 'No tiene',
  correo: 'mock@mock.com',
  codigo_ica: '12345',
  pagina_web: 'www.mock.com',
  nombre_representante: 'Juan Perez',
  tipo_doc_representante: 'cc',
  numero_doc_representante: '1020304050',
  fecha_expedicion: '2010-01-01',
  ciudad_expedicion: 'Bogota',
  nacionalidad: 'Colombiano',
  fecha_nacimiento: '1980-01-01',
  ciudad_nacimiento: 'Bogota',
  profesion: 'Ingeniero',
  correo_representante: 'rep@mock.com',
  telefono_representante: '3109876543',
  direccion_funciones: 'Calle Falsa 123',
  pais_funciones: 'CO',
  departamento_funciones: '11',
  ciudad_funciones: '11001',
  moneda_declaracion: 'COP',
  moneda_declaracion_otra: '',
  actividad_economica: 'Desarrollo de software',
  codigo_ciiu: '6201',
  ingresos_mensuales: '10000000',
  egresos_mensuales: '5000000',
  total_activos: '50000000',
  total_pasivos: '10000000',
  patrimonio: '40000000',
  realiza_operaciones_moneda_extranjera: 'no',
  contacto_ordenes_nombre: 'Ordenes Mock',
  contacto_ordenes_cargo: 'Gerente',
  contacto_ordenes_telefono: '3000000000',
  contacto_ordenes_correo: 'ordenes@mock.com',
  contacto_pagos_nombre: 'Pagos Mock',
  contacto_pagos_cargo: 'Contador',
  contacto_pagos_telefono: '3000000001',
  contacto_pagos_correo: 'pagos@mock.com',
  origen_fondos: 'Actividad Comercial',
  dia_firma: '15',
  mes_firma: '09',
  year_firma: '2026',
  ciudad_firma: 'Bogotá',
};

/** Datos mínimos de una Persona Natural completamente diligenciada */
export const MOCK_DATA_NATURAL = {
  tipo_contraparte: 'proveedor',
  tipo_persona: 'natural',
  tipo_solicitud: 'vinculacion',
  clasificacion_actividad: 'independiente',
  razon_social: 'Juan Natural Perez',
  tipo_identificacion: 'cc',
  numero_identificacion: '1020304050',
  direccion: 'Carrera 10 #20-30',
  pais: 'CO',
  departamento: '11',
  ciudad: '11001',
  telefono: '3001234567',
  fax: 'No tiene',
  correo: 'natural@mock.com',
  codigo_ica: '99999',
  pagina_web: 'No tiene',
  nombre_representante: 'Juan Natural Perez',
  tipo_doc_representante: 'cc',
  numero_doc_representante: '1020304050',
  fecha_expedicion: '2010-01-01',
  ciudad_expedicion: 'Bogota',
  nacionalidad: 'Colombiano',
  fecha_nacimiento: '1980-01-01',
  ciudad_nacimiento: 'Bogota',
  profesion: 'Contador',
  correo_representante: 'natural@mock.com',
  telefono_representante: '3001234567',
  direccion_funciones: 'Carrera 10 #20-30',
  pais_funciones: 'CO',
  departamento_funciones: '11',
  ciudad_funciones: '11001',
  moneda_declaracion: 'COP',
  moneda_declaracion_otra: '',
  actividad_economica: 'Contaduría',
  codigo_ciiu: '6920',
  ingresos_mensuales: '5000000',
  egresos_mensuales: '2000000',
  total_activos: '20000000',
  total_pasivos: '5000000',
  patrimonio: '15000000',
  realiza_operaciones_moneda_extranjera: 'no',
  contacto_ordenes_nombre: 'Juan Natural Perez',
  contacto_ordenes_cargo: 'Propietario',
  contacto_ordenes_telefono: '3001234567',
  contacto_ordenes_correo: 'natural@mock.com',
  contacto_pagos_nombre: 'Juan Natural Perez',
  contacto_pagos_cargo: 'Propietario',
  contacto_pagos_telefono: '3001234567',
  contacto_pagos_correo: 'natural@mock.com',
  origen_fondos: 'Trabajo Independiente',
  dia_firma: '10',
  mes_firma: '10',
  year_firma: '2026',
  ciudad_firma: 'Bogotá',
};

/** Documentos pre-cargados para saltar validación de Step 1 */
export const MOCK_DOCUMENTOS = [
  { id: 1, tipo_documento: 'cedula_representante', nombre_archivo: 'cedula.pdf', tamano: 50000 },
  { id: 2, tipo_documento: 'certificado_existencia', nombre_archivo: 'certificado.pdf', tamano: 50000 },
  { id: 3, tipo_documento: 'estados_financieros', nombre_archivo: 'estados.pdf', tamano: 50000 },
  { id: 4, tipo_documento: 'declaracion_renta', nombre_archivo: 'renta.pdf', tamano: 50000 },
  { id: 5, tipo_documento: 'rut', nombre_archivo: 'rut.pdf', tamano: 50000 },
  { id: 6, tipo_documento: 'referencias_bancarias', nombre_archivo: 'bancos.pdf', tamano: 50000 },
];

/**
 * Configura los interceptores de red para una sesión de prueba.
 * @param {import('@playwright/test').Page} page
 * @param {Object} options
 * @param {Object} options.formData - Datos del formulario a devolver. Default: MOCK_DATA_JURIDICA
 * @param {Array}  options.documentos - Array de documentos. Default: MOCK_DOCUMENTOS
 * @param {string} options.codigoPeticion - Código de petición. Default: 'MOCK-12345'
 * @param {boolean} options.pinInvalido - Si true, el login siempre devuelve 401. Default: false
 * @param {boolean} options.tokenExpirado - Si true, el token devuelve 410. Default: false
 * @param {number} options.stepInicial - Paso inicial del formulario. Default: 1
 */
export async function setupNetworkMocks(page, options = {}) {
  const formDataMock   = options.formData        || MOCK_DATA_JURIDICA;
  const documentosMock = options.documentos      || MOCK_DOCUMENTOS;
  const mockPeticion   = options.codigoPeticion  || 'MOCK-12345';
  const stepInicial    = options.stepInicial      ?? 1;
  const pinInvalido    = options.pinInvalido      ?? false;
  const tokenExpirado  = options.tokenExpirado    ?? false;

  /**
   * Estructura de respuesta plana que espera _adaptarRespuestaServidor.
   * Los campos del formulario van en el TOP LEVEL, no en datos_formulario.
   */
  const formularioMock = {
    id: 9999,
    codigo_peticion: mockPeticion,
    pagina_actual: stepInicial,
    estado: 'BORRADOR',
    updated_at: new Date(Date.now() - 60000).toISOString(), // hace 1 min
    documentos: documentosMock,
    junta_directiva: [],
    accionistas: [],
    beneficiario_final: [],
    referencias_comerciales: [],
    referencias_bancarias: [],
    informacion_bancaria_pagos: [],
    // Campos planos del formulario:
    ...formDataMock,
  };

  // ─── Login por código + PIN ───────────────────────────────────────────────
  await page.route('**/formularios/sesion/recuperar-por-acceso', async route => {
    if (route.request().method() !== 'POST') { await route.continue(); return; }
    if (pinInvalido) {
      await route.fulfill({ status: 401, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Credenciales inválidas' }) });
      return;
    }
    const body = JSON.parse(route.request().postData() || '{}');
    if (body.pin === '0000') {
      await route.fulfill({ status: 401, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Credenciales inválidas' }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(formularioMock),
    });
  });

  // ─── Token URL ────────────────────────────────────────────────────────────
  await page.route('**/accesos-manuales/token/**', async route => {
    const method = route.request().method();
    if (method === 'PATCH') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ valido: true }) });
      return;
    }
    if (method !== 'GET') { await route.continue(); return; }
    if (tokenExpirado || route.request().url().includes('EXPIRED')) {
      await route.fulfill({ status: 410, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Token expirado' }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(formularioMock),
    });
  });

  // ─── Guardar / actualizar formulario (PUT) ───────────────────────────────
  await page.route('**/formularios/9999', async route => {
    if (route.request().method() === 'PUT') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ id: 9999, ...formDataMock }) });
    } else {
      await route.continue();
    }
  });

  // ─── Enviar formulario (POST) ─────────────────────────────────────────────
  await page.route('**/formularios/9999/enviar', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ id: 9999, estado: 'ENVIADO' }) });
    } else {
      await route.continue();
    }
  });

  // ─── Listas de cautela ────────────────────────────────────────────────────
  await page.route('**/listas-cautela/buscar', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ hallazgos: [] }) });
    } else {
      await route.continue();
    }
  });

  // ─── Upload de documento ──────────────────────────────────────────────────
  await page.route('**/formularios/*/documentos', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ id: 99, tipo_documento: 'cedula_representante',
          nombre_archivo: 'mock.pdf', tamano: 50000 }) });
    } else {
      await route.continue();
    }
  });

  // ─── Eliminación de documento ─────────────────────────────────────────────
  await page.route('**/formularios/*/documentos/*', async route => {
    if (route.request().method() === 'DELETE') {
      await route.fulfill({ status: 204 });
    } else {
      await route.continue();
    }
  });

  // ─── IA / prefill ─────────────────────────────────────────────────────────
  await page.route('**/formularios/*/documentos/*/prefill', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          razon_social_extraida: 'EMPRESA MOCK SAS',
          nit_extraido: '900123456',
          digito_verificacion_extraido: '1',
          nombre_representante_extraido: 'Juan Perez',
          numero_doc_representante_extraido: '1020304050',
        }),
      });
    } else {
      await route.continue();
    }
  });
}
