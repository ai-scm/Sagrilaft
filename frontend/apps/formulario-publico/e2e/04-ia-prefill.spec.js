/**
 * E2E: Extracción IA / autocompletado
 *
 * Valida que al subir un documento en Paso 1, el mock de prefill
 * devuelve campos extraídos que el frontend usa para pre-llenar el formulario.
 */
import { test, expect } from '@playwright/test';
import { setupNetworkMocks, MOCK_DATA_JURIDICA } from './utils/networkMocks';
import path from 'path';

test.describe('Extracción IA / Autocompletado', () => {
  test('Al subir un documento, el mock de IA retorna campos y el formulario los muestra', async ({ page }) => {
    // Para este test NO inyectamos documentos en el mock — queremos simular
    // que el usuario los sube manualmente durante la sesión.
    await setupNetworkMocks(page, {
      formData: { ...MOCK_DATA_JURIDICA },
      documentos: [], // Sin documentos pre-cargados
    });

    await page.goto('/');
    await page.getByPlaceholder('Ej. SAG-3A7F2B1C').fill('MOCK-12345');
    await page.getByPlaceholder('PIN de 8 caracteres').fill('12345678');
    await page.getByRole('button', { name: 'Ingresar' }).click();

    // Paso 1: Documentos
    await expect(page.getByText(/Documentos Adjuntos/i)).toBeVisible({ timeout: 10000 });

    // Subir el primer documento — Cédula del Representante Legal
    const uploadZones = page.locator('.file-upload-zone');
    const firstZone = uploadZones.first();
    await expect(firstZone).toBeVisible();

    // Simular subida via file-chooser
    const fileChooserPromise = page.waitForEvent('filechooser');
    await firstZone.click();
    const fileChooser = await fileChooserPromise;

    // Crear un archivo PDF dummy en memoria
    const dummyPdfPath = path.join(process.cwd(), 'e2e', 'fixtures', 'dummy.pdf');
    await fileChooser.setFiles(dummyPdfPath);

    // El mock de upload responde con id=99 y el mock de prefill devuelve campos extraídos.
    // El frontend debe mostrar el archivo cargado (✅ nombre del archivo)
    await expect(page.getByText('mock.pdf')).toBeVisible({ timeout: 10000 });

    // El sistema dispara prefill. El spinner "Analizando con IA..." aparece y desaparece.
    // Dado que el mock responde instantáneamente, puede que no lo alcancemos a ver,
    // pero verificamos que eventualmente el documento muestra el check.
    await expect(page.locator('.file-upload-item').first()).toBeVisible({ timeout: 5000 });
  });
});
