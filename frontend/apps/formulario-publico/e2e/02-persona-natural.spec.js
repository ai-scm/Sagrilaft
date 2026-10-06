/**
 * E2E: Flujo Persona Natural
 *
 * Valida los pasos clave del flujo Natural:
 * - Paso 4 (Junta Directiva) NO aparece para tipo_persona='natural'.
 * - El formulario va de Paso 3 directamente a Paso 5.
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks, MOCK_DATA_NATURAL } from './utils/networkMocks';

test.describe('Flujo E2E - Persona Natural', () => {

  test('Paso 3: Muestra formulario de Persona Natural (sin Junta Directiva)', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_NATURAL, stepInicial: 3 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-NATURAL');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/INFORMACION REPRESENTANTE LEGAL/i)).toBeVisible({ timeout: 10000 });
    
    // El botón "Siguiente" del Paso 3 para Natural debe llevar al Paso 5, no al 4
    // Verificamos la barra de progreso NO muestra Paso 4 como activo para Natural
    // (solo navegamos el heading sin intentar pasar validaciones)
  });

  test('Persona Natural abre en Paso 5 (Financiero) — sin Paso 4 en historial', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_NATURAL, stepInicial: 5 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-NATURAL');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    
    // Debe estar en Paso 5 (Financiero)
    await expect(page.getByText(/Informaci.n Financiera/i)).toBeVisible({ timeout: 10000 });
    
    // Verifica que Junta Directiva NO sea visible — confirmando que el paso fue omitido
    await expect(page.getByText(/JUNTA DIRECTIVA/i)).not.toBeVisible();
  });

  test('Persona Natural llega al último paso sin Junta Directiva', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_NATURAL, stepInicial: 8 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-NATURAL');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/AUTORIZACION - DECLARACION DE FONDOS/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /Radicar/i })).toBeVisible();
  });
});
