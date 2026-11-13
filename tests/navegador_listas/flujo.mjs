// El arnés proporciona un JWT firmado localmente y un expediente ficticio.
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const datos = JSON.parse(await readFile(process.argv[2], 'utf8'));
const mediciones = { fallo_red: datos.fallo_red, alcance: 'Navegador, API y trabajador locales; datos sintéticos' };
const navegador = await chromium.launch({ headless: true });
try {
  const pagina = await navegador.newPage({ acceptDownloads: true });
  const errores = [];
  pagina.on('pageerror', error => errores.push(error.message));
  await pagina.addInitScript(datos => { window.datosPrueba = datos; }, datos);
  await pagina.route(`${datos.url}/`, ruta => ruta.fulfill({ contentType: 'text/html', body: `
    <html lang="es"><div id="root"></div><script type="module">
      import RefreshRuntime from '/@react-refresh';
      RefreshRuntime.injectIntoGlobalHook(window);
      window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => (type) => type;
      window.__vite_plugin_react_preamble_installed__ = true;
      await import('/@vite/client');
      const { default: React } = await import('/node_modules/.vite/deps/react.js');
      const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js');
      const { configurarTokenPortal } = await import('/src/services/api.js');
      configurarTokenPortal(async () => window.datosPrueba.token);
      const { default: ConsultasListas } = await import('/src/components/expedientes/DetalleExpediente/ConsultasListas.jsx');
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(ConsultasListas, {expediente: window.datosPrueba.expediente}));
    </script></html>` }));
  await pagina.goto(datos.url);
  try { await pagina.getByRole('button', { name: 'Consultar contraparte', exact: true }).waitFor({ timeout: 10000 }); }
  catch (error) { throw new Error(`${error.message}; errores=${errores.join(';')}; pantalla=${await pagina.locator('body').innerText()}`); }
  await pagina.getByText('No hay consultas registradas en el módulo nuevo.').waitFor();
  let lecturas = 0;
  let fallos = 0;
  const tiempos = [];
  let recuperar = false;
  let admisiones = 0;
  await pagina.route('**/api/expedientes/*/consultas-listas', async ruta => {
    if (ruta.request().method() === 'POST') admisiones++;
    if (ruta.request().method() === 'GET') {
      lecturas++;
      if (lecturas >= 2 && !recuperar && (datos.fallo_red === 'persistente' || (datos.fallo_red === 'transitorio' && fallos === 0))) {
        fallos++;
        tiempos.push(Date.now());
        return ruta.abort('failed');
      }
    }
    return ruta.continue();
  });
  const inicioIndividual = Date.now();
  await pagina.getByRole('button', { name: 'Consultar contraparte', exact: true }).click();
  if (datos.fallo_red !== 'ninguno') {
    await pagina.getByText('No se pudo actualizar el seguimiento. Reintentaremos automáticamente.').waitFor();
    if (datos.fallo_red === 'persistente') {
      const reintentar = pagina.getByRole('button', { name: 'Reintentar seguimiento', exact: true });
      await reintentar.waitFor({ timeout: 20000 });
      assert.equal(fallos, 3);
      assert(tiempos[1] - tiempos[0] >= 3900);
      assert(tiempos[2] - tiempos[1] >= 7900);
      const anteriores = lecturas;
      await pagina.waitForTimeout(3000);
      assert.equal(lecturas, anteriores, 'El seguimiento pausado no debe seguir consultando');
      recuperar = true;
      await reintentar.click();
    }
  }
  try { await pagina.getByText('Candidatos para revisión humana', { exact: true }).waitFor({ timeout: 15000 }); }
  catch (error) { throw new Error(`${error.message}; pantalla=${await pagina.locator('body').innerText()}; errores=${errores.join(';')}`); }
  mediciones.consulta_individual_hasta_resultado_ms = Date.now() - inicioIndividual;
  assert.equal(await pagina.getByRole('alert').count(), 0, 'El aviso de conexión debe desaparecer al recuperar el seguimiento');
  assert.equal(admisiones, 1, 'Reintentar el seguimiento no debe crear otra consulta');
  if (datos.fallo_red === 'transitorio') assert.equal(fallos, 1);
  await pagina.getByLabel('Justificación').fill('Documento distinto; revisión humana de prueba');
  await pagina.getByLabel('Decisión', { exact: true }).selectOption('DESCARTADA');
  await pagina.getByRole('button', { name: 'Guardar revisión' }).click();
  await pagina.getByRole('listitem').filter({ hasText: 'DESCARTADA: Documento distinto; revisión humana de prueba' }).waitFor();
  const inicioDescarga = Date.now();
  const descargaPendiente = pagina.waitForEvent('download');
  await pagina.getByRole('button', { name: 'Descargar informe conservado' }).click();
  const descarga = await descargaPendiente;
  const contenido = await readFile(await descarga.path());
  assert(contenido.subarray(0, 4).equals(Buffer.from('%PDF')));
  mediciones.descarga_pdf_ms = Date.now() - inicioDescarga;
  const inicioGrupo = Date.now();
  await pagina.getByRole('button', { name: 'Consultar contraparte y representante', exact: true }).click();
  await pagina.waitForFunction(() => document.querySelectorAll('li button').length === 3);
  await pagina.waitForFunction(() => [...document.querySelectorAll('li button')].length === 3 && [...document.querySelectorAll('li button')].every(b => b.textContent.includes('Completada')));
  mediciones.grupo_hasta_historial_completo_ms = Date.now() - inicioGrupo;
  // Recargar demuestra que el historial procede del servidor y no solo del estado de React.
  const inicioRecarga = Date.now();
  await pagina.reload();
  await pagina.waitForFunction(() => document.querySelectorAll('li button').length === 3);
  mediciones.recarga_historial_ms = Date.now() - inicioRecarga;
  if (datos.verificar_presentacion) {
    const niveles = new Set();
    for (let indice = 0; indice < 3; indice++) {
      const respuestaPendiente = pagina.waitForResponse(r => /\/api\/consultas-listas\/[^/]+$/.test(r.url()) && r.request().method() === 'GET');
      await pagina.locator('li button').nth(indice).click();
      const { consulta } = await (await respuestaPendiente).json();
      const candidato = consulta.candidatos[0];
      niveles.add(candidato.nivel);
      await pagina.getByText(`Clasificación de coincidencia: ${candidato.nivel}`, { exact: true }).waitFor();
      const tarjeta = pagina.getByRole('region', { name: `Candidato ${candidato.nombre_principal}`, exact: true });
      await tarjeta.getByText(candidato.explicacion, { exact: true }).waitFor();
      await tarjeta.getByText('Información conservada de la fuente', { exact: true }).click();
      const trazabilidad = pagina.getByText('Trazabilidad de la búsqueda', { exact: true });
      if (await trazabilidad.locator('..').getAttribute('open') === null) await trazabilidad.click();
      await pagina.getByText(consulta.trazabilidad.fuentes[0].generacion_id, { exact: true }).waitFor();
      assert((await pagina.locator('.listas-resultado').innerText()).includes(consulta.cobertura[0].version_id));
      assert((await pagina.locator('.listas-resultado').innerText()).includes(consulta.trazabilidad.fuentes[0].generacion_id));
      const visible = await pagina.locator('.listas-resultado').innerText();
      assert(!/\b(puntaje|porcentaje)\b|\d+(?:[.,]\d+)?\s*%/i.test(visible), 'No deben mostrarse puntajes ni porcentajes');
      assert(visible.includes('SHA-256 del PDF'));
    }
    assert.deepEqual([...niveles].sort(), ['ALTA', 'BAJA', 'MEDIA']);
  }
  assert.equal(errores.length, 0, errores.join('\n'));
  await pagina.screenshot({ path: datos.captura, fullPage: true });
  if (datos.mediciones) await writeFile(datos.mediciones, JSON.stringify(mediciones, null, 2) + '\n');
  console.log('Navegador: consulta, revisión, PDF, grupo e historial tras recarga aprobados');
} finally { await navegador.close(); }
