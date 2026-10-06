/**
 * E2E: Flujo completo Persona Jurídica
 *
 * Valida que un usuario con datos de empresa (jurídica) puede navegar
 * todos los pasos del formulario. Usa stepInicial para saltar directamente
 * a cada paso y verificar que el heading correcto es visible.
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks, MOCK_DATA_JURIDICA } from './utils/networkMocks';

test.describe('Flujo E2E - Persona Jurídica', () => {

  test('Paso 1: Documentos se carga al hacer login', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_JURIDICA, stepInicial: 1 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-JURIDICA');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/Documentos Adjuntos/i)).toBeVisible({ timeout: 10000 });
    // Los documentos del mock ya están cargados (mock inyecta MOCK_DOCUMENTOS)
    await expect(page.locator('.file-upload-item')).toHaveCount(6, { timeout: 5000 });
  });

  test('Paso 2: Info Básica de la Empresa (Jurídica)', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_JURIDICA, stepInicial: 2 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-JURIDICA');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/CLASIFICACION E INFORMACI/i)).toBeVisible({ timeout: 10000 });
    // El campo razon_social debe estar pre-llenado con el valor del mock
    await expect(page.locator('input[name="razon_social"]')).toHaveValue('Empresa Mock SAS');
  });

  test('Paso 3: Representante Legal', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_JURIDICA, stepInicial: 3 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-JURIDICA');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/INFORMACION REPRESENTANTE LEGAL/i)).toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[name="nombre_representante"]')).toHaveValue('Juan Perez');
  });

  test('Paso 4: Junta Directiva (solo Jurídica)', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_JURIDICA, stepInicial: 4 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-JURIDICA');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.locator('h2.section-title', { hasText: /JUNTA DIRECTIVA/i })).toBeVisible({ timeout: 10000 });
  });

  test('Paso 8: Declaraciones y botón Radicar visible', async ({ page }) => {
    await setupNetworkMocks(page, { formData: MOCK_DATA_JURIDICA, stepInicial: 8 });
    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-JURIDICA');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page.getByText(/AUTORIZACION - DECLARACION DE FONDOS/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /Radicar/i })).toBeVisible();
  });
});
