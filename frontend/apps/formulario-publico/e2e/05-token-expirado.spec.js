/**
 * E2E: Token expirado
 *
 * Valida que cuando el usuario accede con un token expirado (?token=EXPIRED),
 * el frontend muestra el mensaje de error adecuado y no carga el formulario.
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks } from './utils/networkMocks';

test.describe('Token Expirado', () => {
  test('Acceso con token expirado muestra mensaje de error', async ({ page }) => {
    // tokenExpirado=true hace que el mock devuelva 410
    await setupNetworkMocks(page, { tokenExpirado: true });

    // Navegar con un token en la URL
    await page.goto('/?token=EXPIRED_TOKEN_123');

    // El frontend debe mostrar el mensaje de acceso expirado
    await expect(page.getByText(/expirado|El acceso ha expirado/i)).toBeVisible({ timeout: 10000 });

    // No debe haber cargado el formulario principal
    await expect(page.getByText(/FORMULARIO DE VINCULACI/i)).not.toBeVisible();
  });

  test('Acceso con PIN incorrecto muestra mensaje de error', async ({ page }) => {
    await setupNetworkMocks(page, { pinInvalido: true });

    await page.goto('/');
    await expect(page.getByText('Acceso Seguro')).toBeVisible({ timeout: 10000 });

    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-12345');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('WRONG123');
    await page.getByRole('button', { name: 'Ingresar' }).click();

    // Mensaje de error de credenciales
    await expect(page.getByText(/incorrecto|C.digo de petici.n o PIN/i)).toBeVisible({ timeout: 10000 });
    
    // La pantalla de ingreso debe permanecer visible
    await expect(page.getByText('Acceso Seguro')).toBeVisible();
  });
});
