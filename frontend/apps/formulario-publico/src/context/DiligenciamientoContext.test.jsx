import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DiligenciamientoProvider, useDiligenciamiento } from './DiligenciamientoContext';
import { api } from '../services/api';
import * as storage from '../utils/borradorStorage';

// Mocks
vi.mock('../services/api', () => ({
  api: {
    resolverTokenDiligenciamiento: vi.fn(),
    recuperarSesionPorAcceso: vi.fn(),
  }
}));

vi.mock('../utils/borradorStorage', () => ({
  leerBorradorDeStorage: vi.fn(),
  eliminarBorradorDeStorage: vi.fn(),
  borradorEsFormularioEnviado: vi.fn(),
}));

const mockReplaceState = vi.fn();
Object.defineProperty(window, 'history', {
  value: { replaceState: mockReplaceState },
  writable: true
});

let originalLocation;

describe('DiligenciamientoContext', () => {
  beforeEach(() => {
    originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, search: '', pathname: '/test' };
    vi.clearAllMocks();
  });

  afterEach(() => {
    window.location = originalLocation;
  });

  const getHook = () => renderHook(() => useDiligenciamiento(), { wrapper: DiligenciamientoProvider });

  describe('1. Token por URL (Autenticación sin contraseña)', () => {
    it('inicia sesión automáticamente y limpia la URL si el token es válido', async () => {
      window.location.search = '?token=VALID_TOKEN';
      api.resolverTokenDiligenciamiento.mockResolvedValueOnce({ id: 1, razon_social: 'Token Corp' });

      const { result } = getHook();

      // Inicialmente está cargando
      expect(result.current.cargando).toBe(true);

      // Esperar a que resuelva la promesa del useEffect
      await vi.waitFor(() => {
        expect(result.current.cargando).toBe(false);
      });

      expect(result.current.sesionActiva).toBe(true);
      expect(result.current.snapshotInicial.razon_social).toBe('Token Corp');
      expect(mockReplaceState).toHaveBeenCalledWith({}, '', '/test');
    });

    it('establece el error correcto si el token expiró', async () => {
      window.location.search = '?token=EXPIRED_TOKEN';
      api.resolverTokenDiligenciamiento.mockRejectedValueOnce({ code: 'ACCESO_EXPIRADO' });

      const { result } = getHook();

      await vi.waitFor(() => {
        expect(result.current.cargando).toBe(false);
      });

      expect(result.current.sesionActiva).toBe(false);
      expect(result.current.error).toContain('El enlace ha expirado');
    });
  });

  describe('2. Evaluación Inicial de Borrador Local', () => {
    it('ignora borrador y lo elimina si ya fue enviado', async () => {
      storage.leerBorradorDeStorage.mockReturnValueOnce({ codigoPeticion: 'XYZ' });
      storage.borradorEsFormularioEnviado.mockReturnValueOnce(true);

      const { result } = getHook();

      expect(storage.eliminarBorradorDeStorage).toHaveBeenCalled();
      expect(result.current.sesionActiva).toBe(false);
      expect(result.current.borradorLocal).toBeNull();
    });

    it('hace bypass y da acceso directo si el borrador es puramente local (sin credenciales)', async () => {
      // Un borrador sin formularioId ni codigoPeticion es un borrador no sincronizado (AI/Local only)
      storage.leerBorradorDeStorage.mockReturnValueOnce({ razon_social: 'AI Local' });
      storage.borradorEsFormularioEnviado.mockReturnValueOnce(false);

      const { result } = getHook();

      expect(result.current.sesionActiva).toBe(true);
      expect(result.current.snapshotInicial.razon_social).toBe('AI Local');
      expect(result.current.borradorLocal).toBeNull(); // No lo guarda en borradorLocal, lo pasa a snapshot
    });

    it('expone el borradorLocal pero no inicia sesión si requiere código/PIN', async () => {
      storage.leerBorradorDeStorage.mockReturnValueOnce({ formularioId: 123, codigoPeticion: 'XYZ' });
      storage.borradorEsFormularioEnviado.mockReturnValueOnce(false);

      const { result } = getHook();

      expect(result.current.sesionActiva).toBe(false);
      expect(result.current.borradorLocal.codigoPeticion).toBe('XYZ');
    });
  });

  describe('3. Ingreso Manual y Mapeo de Errores', () => {
    it('inicia sesión, elimina borrador local de persistencia e inyecta precedente para IA', async () => {
      // 1. Simular que había un borrador guardado en el navegador (con datos de IA)
      storage.leerBorradorDeStorage.mockReturnValueOnce({ formularioId: 123, codigoPeticion: 'XYZ', campos_sugeridos: true });
      storage.borradorEsFormularioEnviado.mockReturnValueOnce(false);

      const { result } = getHook();
      
      expect(result.current.borradorLocal).toBeTruthy();

      // 2. Simular que el usuario hace login
      api.recuperarSesionPorAcceso.mockResolvedValueOnce({ id: 123, estado: 'BORRADOR' });

      await act(async () => {
        await result.current.ingresarConCredenciales('XYZ', 'PIN');
      });

      expect(result.current.sesionActiva).toBe(true);
      
      // 3. Verificar la inyección del borrador local precedente para la hidratación!
      expect(result.current.snapshotInicial._borradorLocalPrecedente.campos_sugeridos).toBe(true);
      
      // 4. Verificar que se borró de la persistencia y de la vista del Ingreso
      expect(storage.eliminarBorradorDeStorage).toHaveBeenCalled();
      expect(result.current.borradorLocal).toBeNull();
    });

    it('mapea código CREDENCIALES_INVALIDAS a un texto de UI amigable', async () => {
      const { result } = getHook();

      api.recuperarSesionPorAcceso.mockRejectedValueOnce({ code: 'CREDENCIALES_INVALIDAS' });

      await act(async () => {
        await result.current.ingresarConCredenciales('XYZ', 'MALPIN');
      });

      expect(result.current.error).toBe('Código de petición o PIN incorrecto. Verifique los datos.');
      expect(result.current.sesionActiva).toBe(false);
    });

    it('maneja el error de servidor genérico', async () => {
      const { result } = getHook();
      api.recuperarSesionPorAcceso.mockRejectedValueOnce({ code: 'OTRO_ERROR' });
      await act(async () => {
        await result.current.ingresarConCredenciales('XYZ', 'PIN');
      });
      expect(result.current.error).toBe('Error al conectar con el servidor. Intente nuevamente.');
    });
  });

  describe('4. Acciones de Sesión', () => {
    it('cierra sesión con mensaje de error personalizado o genérico', async () => {
      const { result } = getHook();
      
      act(() => {
        result.current.cerrarSesion('Sesión finalizada manualmente');
      });
      
      expect(result.current.sesionActiva).toBe(false);
      expect(result.current.snapshotInicial).toBeNull();
      expect(result.current.error).toBe('Sesión finalizada manualmente');
      
      act(() => {
        result.current.cerrarSesion();
      });
      expect(result.current.error).toBe('Su sesión ha expirado.');
    });

    it('descarta el borrador y limpia el almacenamiento', async () => {
      const { result } = getHook();
      
      act(() => {
        result.current.descartarBorrador();
      });
      
      expect(storage.eliminarBorradorDeStorage).toHaveBeenCalled();
      expect(result.current.borradorLocal).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });
});
