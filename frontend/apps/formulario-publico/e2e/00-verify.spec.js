/**
 * E2E: Verificación de infraestructura Playwright
 * Confirma que el frontend arranca, los mocks interceptan el login
 * y el formulario principal es accesible.
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks } from './utils/networkMocks';

test.describe('Verificación Base', () => {
  test('Playwright arranca el frontend y el login funciona con mocks', async ({ page }) => {
    await setupNetworkMocks(page);
    await page.goto('/');

    // Pantalla de ingreso visible
    await expect(page.getByText('Acceso Seguro')).toBeVisible({ timeout: 10000 });

    // Llenar credenciales
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-12345');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');

    // Login
    await page.getByRole('button', { name: 'Ingresar' }).click();

    // Debe aparecer el formulario principal
    await expect(page.getByText(/FORMULARIO DE VINCULACI/i)).toBeVisible({ timeout: 10000 });
  });
});
