import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useFormulario } from './useFormulario';
import * as validacionHooks from './useFormValidacion';
import * as persistenciaHooks from '../persistencia/useFormPersistencia';
import * as recuperacionHooks from '../persistencia/useRecuperacionSesion';
import { api } from '../../services/api';
import { JUNTA_INICIAL } from './useTablasDinamicas';

// Mocks
vi.mock('../../services/api', () => ({
  api: {
    crearFormulario: vi.fn(),
    actualizarFormulario: vi.fn(),
    subirDocumento: vi.fn(),
    eliminarDocumento: vi.fn(),
    enviarFormulario: vi.fn(),
  }
}));

vi.mock('../../data/formularioConfig', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    validarDocumentosRequeridos: vi.fn(() => ({})),
  };
});

vi.mock('../../utils/validacionTablas', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    validarTablasPaso4: vi.fn(() => ({})),
    validarTablasPaso6: vi.fn(() => ({})),
    validarTablasPaso7: vi.fn(() => ({})),
  };
});

vi.mock('../persistencia/useFormPersistencia', () => ({
  useFormPersistencia: vi.fn()
}));

vi.mock('../persistencia/useRecuperacionSesion', () => ({
  useRecuperacionSesion: vi.fn()
}));

vi.mock('./useFormValidacion', () => ({
  useFormValidacion: vi.fn(() => ({
    errors: {},
    validarPaso: vi.fn(() => ({})),
    aplicarErrores: vi.fn(),
    limpiarError: vi.fn()
  }))
}));

// Mock `window.scrollTo` as it's called on handleNext
global.window.scrollTo = vi.fn();

describe('useFormulario', () => {
  const mockAplicarErrores = vi.fn();
  const mockValidarPaso = vi.fn(() => ({}));
  const mockLimpiarError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    
    vi.mocked(validacionHooks.useFormValidacion).mockReturnValue({
      errors: {},
      validarPaso: mockValidarPaso,
      aplicarErrores: mockAplicarErrores,
      limpiarError: mockLimpiarError
    });
    
    // Default mock returns for persistence/recovery hooks to avoid breaking destructuring
    vi.mocked(persistenciaHooks.useFormPersistencia).mockReturnValue({
      lastSaved: null,
      limpiarBorrador: vi.fn(),
      guardarBorradorLocal: vi.fn()
    });
    
    vi.mocked(recuperacionHooks.useRecuperacionSesion).mockReturnValue({
      credencialesRef: { current: null },
      abrirConError: vi.fn()
    });
  });

  describe('1. Inicialización y Estado Base', () => {
    it('initializes with default values (Step 1)', () => {
      const { result } = renderHook(() => useFormulario());
      
      expect(result.current.step).toBe(1);
      expect(result.current.formData).toEqual({});
      expect(result.current.juntaDirectiva).toEqual(JUNTA_INICIAL);
      expect(result.current.accionistas).toEqual([{}]);
      expect(result.current.beneficiarios).toEqual([{}]);
    });
  });

  describe('2. Flujo Exclusivo: Persona Natural', () => {
    it('purges enterprise-only variables when changing to natural', () => {
      const { result } = renderHook(() => useFormulario());
      
      // Act: Set form data as if it were a juridica first
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
        result.current.handleChange({ target: { name: 'gran_contribuyente', value: 'true', type: 'radio' } });
        result.current.handleChange({ target: { name: 'entidad_oficial', value: 'false', type: 'radio' } });
      });
      
      expect(result.current.formData.gran_contribuyente).toBe(true);
      
      // Act: Change back to natural
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'natural' } });
      });
      
      // Assert: Enterprise vars are purged
      expect(result.current.formData.tipo_persona).toBe('natural');
      expect(result.current.formData.gran_contribuyente).toBe('');
      expect(result.current.formData.entidad_oficial).toBe('');
    });

    it('resets Step 4 tables when changing to natural', () => {
      const { result } = renderHook(() => useFormulario());
      
      // Act: Add a member as juridica
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
        result.current.addJuntaMember();
      });
      
      expect(result.current.juntaDirectiva.length).toBe(2); // JUNTA_INICIAL has 1 + 1 = 2
      
      // Act: Change to natural
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'natural' } });
      });
      
      // Assert: Tables reset
      expect(result.current.juntaDirectiva).toEqual(JUNTA_INICIAL);
      expect(result.current.accionistas).toEqual([{}]);
    });

    it('builds payload with empty arrays for step 4 when natural, regardless of state', async () => {
      const { result } = renderHook(() => useFormulario());
      
      // Act: Setup as natural, but artificially populate the tables
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'natural' } });
        result.current.handleJuntaChange(0, 'nombres', 'Juan Perez');
      });
      
      // Trigger a sync by saving draft
      api.crearFormulario.mockResolvedValueOnce({ id: 123, codigo_peticion: 'ABC' });
      await act(async () => {
        await result.current.handleSaveDraft();
      });
      
      // Assert payload sent to API
      expect(api.crearFormulario).toHaveBeenCalled();
      const payload = api.crearFormulario.mock.calls[0][0];
      
      expect(payload.tipo_persona).toBe('natural');
      expect(payload.junta_directiva).toEqual([]);
      expect(payload.accionistas).toEqual([]);
      expect(payload.beneficiario_final).toEqual([]);
    });

    it('clears all corporate and natural validation errors when changing to natural', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'natural' } });
      });
      
      expect(mockLimpiarError.mock.calls.some(call => call[0] === 'actividad_clasificacion')).toBe(true);
      expect(mockLimpiarError.mock.calls.some(call => call[0] === 'ciudad_residencia')).toBe(true);
      expect(mockLimpiarError).toHaveBeenCalledWith('tipo_persona');
      expect(mockAplicarErrores).toHaveBeenCalled(); // To clear Paso 4 tables errors
    });
  });

  describe('3. Flujo Exclusivo: Persona Jurídica', () => {
    it('purges natural-only variables when changing to juridica', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'natural' } });
        result.current.handleChange({ target: { name: 'ciudad_residencia', value: 'Bogota' } });
      });
      
      expect(result.current.formData.ciudad_residencia).toBe('Bogota');
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
      });
      
      expect(result.current.formData.tipo_persona).toBe('juridica');
      expect(result.current.formData.ciudad_residencia).toBe('');
    });

    it('mutates corporate tables via exposed helpers', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
        result.current.handleJuntaChange(0, 'nombres', 'Carlos');
        result.current.addJuntaMember();
      });
      
      expect(result.current.juntaDirectiva.length).toBe(2);
      expect(result.current.juntaDirectiva[0].nombres).toBe('Carlos');
      
      act(() => {
        result.current.eliminarJuntaMember(1);
      });
      
      expect(result.current.juntaDirectiva.length).toBe(1);
    });

    it('purges empty rows from tables when building payload', async () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
        result.current.handleJuntaChange(0, 'nombres', 'Carlos');
        result.current.handleJuntaChange(0, 'apellidos', 'Perez');
        // El resto (índice 1) queda vacío
      });
      
      api.crearFormulario.mockResolvedValueOnce({ id: 123, codigo_peticion: 'ABC' });
      await act(async () => {
        await result.current.handleSaveDraft();
      });
      
      const payload = api.crearFormulario.mock.calls[0][0];
      
      // Expected: solo se envía la fila no vacía
      expect(payload.junta_directiva.length).toBe(1);
      expect(payload.junta_directiva[0].nombres).toBe('Carlos');
    });
  });

  describe('4. Lógica de Cascada y Limpieza de Errores', () => {
    it('clears dependent fields when Moneda Extranjera is set to false', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleMonedaExtranjeraChange(true);
        result.current.handleChange({ target: { name: 'paises_operaciones', value: 'USA' } });
        result.current.handleTiposTransaccionChange(['importacion', 'otras']);
        result.current.handleChange({ target: { name: 'tipos_transaccion_otros', value: 'Servicios' } });
      });
      
      expect(result.current.formData.paises_operaciones).toBe('USA');
      expect(result.current.formData.tipos_transaccion).toContain('importacion');
      expect(result.current.formData.tipos_transaccion_otros).toBe('Servicios');
      
      act(() => {
        result.current.handleMonedaExtranjeraChange(false);
      });
      
      expect(result.current.formData.paises_operaciones).toBe('');
      expect(result.current.formData.tipos_transaccion).toEqual([]);
      expect(result.current.formData.tipos_transaccion_otros).toBe('');
    });

    it('clears ID number when ID type changes', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_identificacion', value: 'CC' } });
        result.current.handleChange({ target: { name: 'numero_identificacion', value: '123456' } });
      });
      
      expect(result.current.formData.numero_identificacion).toBe('123456');
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_identificacion', value: 'NIT' } });
      });
      
      expect(result.current.formData.tipo_identificacion).toBe('NIT');
      expect(result.current.formData.numero_identificacion).toBe('');
    });

    it('forces NA on actividad_especifica and moneda_declaracion_otra when not OTRA', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleActividadChange({ target: { value: 'Comercio' } });
        result.current.handleMonedaDeclaracionChange({ target: { value: 'USD' } });
      });
      
      expect(result.current.formData.actividad_clasificacion).toBe('Comercio');
      expect(result.current.formData.actividad_especifica).toBe('NA');
      expect(result.current.formData.moneda_declaracion).toBe('USD');
      expect(result.current.formData.moneda_declaracion_otra).toBe('NA');

      act(() => {
        result.current.handleActividadChange({ target: { value: 'Otra' } });
        result.current.handleMonedaDeclaracionChange({ target: { value: 'OTRA' } });
      });

      expect(result.current.formData.actividad_especifica).toBe('');
      expect(result.current.formData.moneda_declaracion_otra).toBe('');
    });
  });

  describe('5. Validación y Navegación (Gatekeeping)', () => {
    it('blocks handleNext when validation errors exist and populates errors state', () => {
      // Mockear validarDocumentosRequeridos del config para que retorne errores
      vi.mocked(validacionHooks.useFormValidacion).mockReturnValue({
        errors: {},
        validarPaso: vi.fn(() => ({ documento_identidad: 'Falta documento' })),
        aplicarErrores: mockAplicarErrores,
        limpiarError: vi.fn()
      });

      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleNext(); // Falla porque simulamos que hay errores
      });
      
      expect(result.current.step).toBe(1); // Se bloquea en el paso 1
      expect(mockAplicarErrores).toHaveBeenCalled(); // Se llamó para aplicar el error
    });

    it('advances step on handleNext when no errors exist', () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleChange({ target: { name: 'tipo_persona', value: 'juridica' } });
      });
      
      act(() => {
        result.current.handleNext();
      });

      // No errors mocked, so it advances to next visible step (2)
      expect(result.current.step).toBe(2);
    });
  });

  describe('6. Purgado de Tablas de Paso 6 y 7', () => {
    it('purges empty rows from Referencias and Info Bancaria on save', async () => {
      const { result } = renderHook(() => useFormulario());
      
      act(() => {
        result.current.handleReferenciaChange(0, 'nombre_establecimiento', 'Ref 1');
        result.current.handleInfoBancariaPagosChange(0, 'entidad_bancaria', 'Banco 1');
      });
      
      api.crearFormulario.mockResolvedValueOnce({ id: 123, codigo_peticion: 'ABC' });
      await act(async () => {
        await result.current.handleSaveDraft();
      });
      
      const payload = api.crearFormulario.mock.calls[0][0];
      
      expect(payload.referencias_comerciales.length).toBe(1);
      expect(payload.referencias_comerciales[0].nombre_establecimiento).toBe('Ref 1');
      expect(payload.informacion_bancaria_pagos.length).toBe(1);
      expect(payload.informacion_bancaria_pagos[0].entidad_bancaria).toBe('Banco 1');
    });
  });

  describe('7. Lógica de Archivos e IA (Extracción y Borrado)', () => {
    it('merges suggested fields from AI when file is uploaded', async () => {
      const { result } = renderHook(() => useFormulario());
      
      api.crearFormulario.mockResolvedValueOnce({ id: 123, codigo_peticion: 'ABC' });
      api.subirDocumento.mockResolvedValueOnce({
        id: 1,
        extraccion_exitosa: true,
        campos_sugeridos: { razon_social: 'Empresa AI SAS' }
      });
      
      await act(async () => {
        await result.current.handleFileChange('rut', new File([''], 'rut.pdf'));
      });
      
      expect(result.current.documentos.rut.id).toBe(1);
      expect(result.current.formData.razon_social).toBe('Empresa AI SAS');
    });

    it('clears associated formData when a document is deleted', async () => {
      const { result } = renderHook(() => useFormulario());
      
      // Inject some state
      act(() => {
        result.current.handleChange({ target: { name: 'razon_social', value: 'Borrame' } });
      });
      
      // Manually set the doc
      api.crearFormulario.mockResolvedValueOnce({ id: 123, codigo_peticion: 'ABC' });
      api.subirDocumento.mockResolvedValueOnce({ id: 2, extraccion_exitosa: true });
      await act(async () => {
        await result.current.handleFileChange('rut', new File([''], 'rut.pdf'));
      });
      
      // Remove the doc
      act(() => {
        result.current.handleRemoveFile('rut');
      });
      
      api.eliminarDocumento.mockResolvedValueOnce({});
      await act(async () => {
        await result.current.confirmarEliminacion();
      });
      
      // 'razon_social' is one of the fields extracted from RUT in mapeoDocumentos
      // So it should be cleared!
      expect(result.current.documentos.rut).toBeUndefined();
      expect(result.current.formData.razon_social).toBe('');
    });
  });

  describe('8. Buscador Inverso de Errores (handleSubmit)', () => {
    it('navigates to the lowest step with errors when handleSubmit is called', async () => {
      const { result } = renderHook(() => useFormulario());
      
      // Advance to step 8 artificially
      act(() => {
        result.current.irAPasoCorreccion(8);
      });
      expect(result.current.step).toBe(8);
      
      // Mock the submit to fail due to missing fields in Step 3
      // We will spy on the mockValidarPaso to return an error for step 3
      mockValidarPaso.mockImplementation((s) => {
        if (s === 3) return { nombre_representante: 'Falta nombre' };
        return {};
      });
      
      await act(async () => {
        try { await result.current.handleSubmit(); } catch (e) { console.log("ERROR IN SUBMIT:", e); }
      });
      
      // Should have jumped back to Step 3
      expect(result.current.step).toBe(3);
    });
  });

  describe('9. Envío Final (handleSave)', () => {
    it('procesa el envío exitoso', async () => {
      // Mock window.alert para que no rompa tests si falla algo
      const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
      api.crearFormulario.mockResolvedValueOnce({ id: 1, codigo_peticion: 'ABC' });
      api.enviarFormulario.mockResolvedValueOnce({});
      
      const { result } = renderHook(() => useFormulario());
      
      // Forzar que el validador diga que todo está bien
      mockValidarPaso.mockReturnValue({});

      await act(async () => {
        // Avanzamos al paso 7 y seteamos los checks para evitar errores
        result.current.handleChange({ target: { name: 'autorizacion_datos', type: 'checkbox', checked: true } });
        result.current.handleChange({ target: { name: 'declaracion_origen_fondos', type: 'checkbox', checked: true } });
        result.current.irAPasoCorreccion(7);
      });

      await act(async () => {
        // Ejecutamos handleSubmit. Si no hay errores, llama internamente a handleSave (enviarFormulario)
        try { await result.current.handleSubmit(); } catch (e) { console.log("ERROR IN SUBMIT:", e); }
      });

      expect(api.enviarFormulario).toHaveBeenCalled();
      expect(result.current.submitted).toBe(true);
      expect(result.current.saving).toBe(false);
      alertMock.mockRestore();
    });

    it('abre modal de error (401) si las credenciales expiraron', async () => {
      api.crearFormulario.mockResolvedValueOnce({ id: 1, codigo_peticion: 'ABC' });
      api.enviarFormulario.mockRejectedValueOnce({ status: 401 });
      const { result } = renderHook(() => useFormulario());
      mockValidarPaso.mockReturnValue({});

      await act(async () => {
        result.current.handleChange({ target: { name: 'autorizacion_datos', type: 'checkbox', checked: true } });
        result.current.handleChange({ target: { name: 'declaracion_origen_fondos', type: 'checkbox', checked: true } });
        result.current.irAPasoCorreccion(7);
      });

      await act(async () => {
        try { await result.current.handleSubmit(); } catch (e) { console.log("ERROR IN SUBMIT:", e); }
      });

      // Se debió llamar al context mockAbrirConError (expuesto en recuperacion)
      expect(result.current.recuperacion.abrirConError).toHaveBeenCalledWith(expect.stringContaining('Su sesión ha expirado'));
      expect(result.current.saving).toBe(false);
    });

    it('muestra alert con error 410 (enlace expirado)', async () => {
      const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
      api.crearFormulario.mockResolvedValueOnce({ id: 1, codigo_peticion: 'ABC' });
      api.enviarFormulario.mockRejectedValueOnce({ status: 410 });
      const { result } = renderHook(() => useFormulario());
      mockValidarPaso.mockReturnValue({});

      await act(async () => {
        result.current.handleChange({ target: { name: 'autorizacion_datos', type: 'checkbox', checked: true } });
        result.current.handleChange({ target: { name: 'declaracion_origen_fondos', type: 'checkbox', checked: true } });
        result.current.irAPasoCorreccion(7);
      });

      await act(async () => {
        try { await result.current.handleSubmit(); } catch (e) { console.log("ERROR IN SUBMIT:", e); }
      });

      expect(alertMock).toHaveBeenCalledWith(expect.stringContaining('El acceso ha expirado'));
      alertMock.mockRestore();
    });

    it('muestra alert con mensaje genérico si hay otro error', async () => {
      const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
      api.crearFormulario.mockResolvedValueOnce({ id: 1, codigo_peticion: 'ABC' });
      api.enviarFormulario.mockRejectedValueOnce({ message: 'Error de servidor 500' });
      const { result } = renderHook(() => useFormulario());
      mockValidarPaso.mockReturnValue({});

      await act(async () => {
        result.current.handleChange({ target: { name: 'autorizacion_datos', type: 'checkbox', checked: true } });
        result.current.handleChange({ target: { name: 'declaracion_origen_fondos', type: 'checkbox', checked: true } });
        result.current.irAPasoCorreccion(7);
      });

      await act(async () => {
        try { await result.current.handleSubmit(); } catch (e) { console.log("ERROR IN SUBMIT:", e); }
      });

      expect(alertMock).toHaveBeenCalledWith(expect.stringContaining('Error de servidor 500'));
      alertMock.mockRestore();
    });
  });
});
