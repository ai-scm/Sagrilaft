/**
 * E2E: Persistencia y recuperación de borrador
 *
 * Valida que cuando el mock devuelve un formulario en un paso avanzado,
 * el frontend restaura ese estado y navega al paso correcto.
 * También valida el flujo de borrador local (localStorage).
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks, MOCK_DATA_JURIDICA } from './utils/networkMocks';

test.describe('Persistencia y Recuperación de Borrador', () => {

  test('Restaura el formulario en el paso guardado (pagina_actual = 5)', async ({ page }) => {
    // Simular que el backend dice que el usuario iba en el Paso 5 (Financiero)
    await setupNetworkMocks(page, {
      formData: MOCK_DATA_JURIDICA,
      stepInicial: 5,
    });

    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-12345');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();

    // El formulario debe abrirse directamente en el Paso 5: Financiero
    await expect(page.getByText(/Informaci.n Financiera/i)).toBeVisible({ timeout: 10000 });
    
    // No debe estar en Paso 1 (Documentos)
    await expect(page.getByText(/Documentos Adjuntos/i)).not.toBeVisible();
  });

  test('Borrador local: detecta sesión previa y muestra botón de recuperación', async ({ page }) => {
    await setupNetworkMocks(page);

    // Inyectamos un borrador en localStorage antes de cargar la página
    await page.goto('/');
    await page.evaluate(() => {
      const borrador = {
        formularioId: 9999,
        codigo_peticion: 'MOCK-12345',
        guardadoEn: new Date().toISOString(),
        step: 3,
        formData: { razon_social: 'Empresa desde borrador', tipo_persona: 'juridica' },
        documentos: {},
        juntaDirectiva: [],
        accionistas: [],
        beneficiarios: [],
        referenciasComerciales: [],
        referenciasBancarias: [],
        infoBancariaPagos: [],
      };
      localStorage.setItem('sagrilaft_autosave', JSON.stringify(borrador));
    });

    // Recarga la página para que el context lea el borrador
    await page.reload();

    // Debe mostrar la pantalla de ingreso con aviso de borrador previo
    await expect(page.getByText(/Borrador guardado/i)).toBeVisible({ timeout: 10000 });
    
    // El botón de "Ingresar con otras credenciales" debe estar disponible
    await expect(page.getByRole('button', { name: /Ingresar con otras credenciales/i })).toBeVisible();
  });
});
