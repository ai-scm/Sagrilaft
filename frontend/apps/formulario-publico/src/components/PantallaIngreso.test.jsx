import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PantallaIngreso from './PantallaIngreso';
import { useDiligenciamiento } from '../context/DiligenciamientoContext';

// Mock de useDiligenciamiento
vi.mock('../context/DiligenciamientoContext', () => ({
  useDiligenciamiento: vi.fn(),
}));

describe('PantallaIngreso', () => {
  const mockIngresarConCredenciales = vi.fn();
  const mockDescartarBorrador = vi.fn();

  // Función de ayuda para simular el contexto
  const setMockContext = (overrides = {}) => {
    useDiligenciamiento.mockReturnValue({
      ingresarConCredenciales: mockIngresarConCredenciales,
      cargando: false,
      error: null,
      borradorLocal: null,
      descartarBorrador: mockDescartarBorrador,
      ...overrides,
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('1. Estado Inicial (Usuario Nuevo / Sin Borrador)', () => {
    beforeEach(() => setMockContext());

    it('renderiza la interfaz básica para un usuario sin borrador', () => {
      render(<PantallaIngreso />);
      
      // Títulos y logos
      expect(screen.getByText('SAGRILAFT')).toBeInTheDocument();
      expect(screen.getByText('Acceso Seguro')).toBeInTheDocument();
      
      // Instrucciones base
      expect(screen.getByText(/Para iniciar o continuar, ingrese el código/i)).toBeInTheDocument();

      // Inputs vacíos
      const codigoInput = screen.getByLabelText(/Código de petición/i);
      const pinInput = screen.getByLabelText(/PIN de acceso/i);
      
      expect(codigoInput).toHaveValue('');
      expect(pinInput).toHaveValue('');
      
      // Botón deshabilitado
      const submitBtn = screen.getByRole('button', { name: /ingresar/i });
      expect(submitBtn).toBeDisabled();
      
      // No existe botón de descarte
      expect(screen.queryByRole('button', { name: /ingresar con otras credenciales/i })).not.toBeInTheDocument();
    });
  });

  describe('2. Recuperación de Borrador Local (borradorLocal presente)', () => {
    it('muestra el banner de recuperación con fecha exacta, pre-llena código y mantiene PIN vacío', () => {
      const fechaMock = '2026-09-30T10:00:00.000Z';
      setMockContext({
        borradorLocal: {
          codigoPeticion: 'BORRADOR-123',
          guardadoEn: fechaMock
        }
      });

      render(<PantallaIngreso />);

      // Calcular la fecha tal cual la genera el componente para evitar falsos positivos
      const fechaFormateada = new Date(fechaMock).toLocaleString('es-CO', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });

      // Banner y mensaje de recuperación con aserción estricta de fecha
      expect(screen.getByText(`Borrador guardado: ${fechaFormateada}`)).toBeInTheDocument();
      expect(screen.getByText(/retomar donde lo dejó/i)).toBeInTheDocument();

      // Pre-llenado de código
      const codigoInput = screen.getByLabelText(/Código de petición/i);
      expect(codigoInput).toHaveValue('BORRADOR-123');
      
      // Seguridad: el PIN debe permanecer vacío
      const pinInput = screen.getByLabelText(/PIN de acceso/i);
      expect(pinInput).toHaveValue('');
      
      // Botón de descarte presente y funcional
      const descartarBtn = screen.getByRole('button', { name: /ingresar con otras credenciales/i });
      expect(descartarBtn).toBeInTheDocument();
      
      fireEvent.click(descartarBtn);
      expect(mockDescartarBorrador).toHaveBeenCalled();
    });
  });

  describe('3. Interacción y Limpieza de Entradas (Submit)', () => {
    beforeEach(() => setMockContext());

    it('habilita el botón de envío y recorta/mayusculiza los inputs al enviar', () => {
      render(<PantallaIngreso />);
      
      const codigoInput = screen.getByLabelText(/Código de petición/i);
      const pinInput = screen.getByLabelText(/PIN de acceso/i);
      const submitBtn = screen.getByRole('button', { name: /ingresar/i });

      // Botón inicia deshabilitado
      expect(submitBtn).toBeDisabled();

      // Escribir solo un campo no habilita el botón
      fireEvent.change(codigoInput, { target: { value: ' sag-abc ' } });
      expect(submitBtn).toBeDisabled();

      // Escribir ambos lo habilita
      fireEvent.change(pinInput, { target: { value: ' pin123 ' } });
      expect(submitBtn).toBeEnabled();

      // Enviar formulario (simulando submit nativo de formulario)
      fireEvent.submit(codigoInput.closest('form'));

      // Debe llamar a ingresarConCredenciales con valores formateados
      expect(mockIngresarConCredenciales).toHaveBeenCalledWith('SAG-ABC', 'PIN123');
    });

    it('bloquea el submit (gatekeeping) si se presiona ENTER con campos vacíos', () => {
      render(<PantallaIngreso />);
      const codigoInput = screen.getByLabelText(/Código de petición/i);
      
      // Submit nativo (Enter) pero con campos vacíos
      fireEvent.submit(codigoInput.closest('form'));
      
      // El if(puedeEnviar) debe bloquear la llamada
      expect(mockIngresarConCredenciales).not.toHaveBeenCalled();
    });
  });

  describe('4. Flujo de Carga (cargando: true)', () => {
    it('renderiza únicamente el loader y oculta el formulario', () => {
      setMockContext({ cargando: true });
      render(<PantallaIngreso />);

      expect(screen.getByText('Validando acceso seguro...')).toBeInTheDocument();
      // No debería haber inputs ni botones de envío
      expect(screen.queryByLabelText(/Código de petición/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /ingresar/i })).not.toBeInTheDocument();
    });
  });

  describe('5. Manejo de Errores de Autenticación', () => {
    it('muestra el mensaje de error cuando falla la autenticación', () => {
      setMockContext({ error: 'El PIN ingresado es incorrecto o ha expirado.' });
      render(<PantallaIngreso />);

      const errorAlert = screen.getByRole('alert');
      expect(errorAlert).toBeInTheDocument();
      expect(errorAlert).toHaveTextContent('El PIN ingresado es incorrecto o ha expirado.');
    });
  });

  describe('6. Estilos de Interacción Visual (Focus/Blur)', () => {
    beforeEach(() => setMockContext());

    it('aplica borderColor primario al enfocar inputs y lo remueve al quitar foco', () => {
      render(<PantallaIngreso />);
      const codigoInput = screen.getByLabelText(/Código de petición/i);
      const pinInput = screen.getByLabelText(/PIN de acceso/i);

      // Estado base: color gris
      expect(codigoInput.style.borderColor).toBe('var(--gray-200)');
      expect(pinInput.style.borderColor).toBe('var(--gray-200)');

      // Focus en código
      fireEvent.focus(codigoInput);
      expect(codigoInput.style.borderColor).toBe('var(--primary-500)');
      expect(pinInput.style.borderColor).toBe('var(--gray-200)');

      // Blur en código, Focus en PIN
      fireEvent.blur(codigoInput);
      fireEvent.focus(pinInput);
      
      expect(codigoInput.style.borderColor).toBe('var(--gray-200)');
      expect(pinInput.style.borderColor).toBe('var(--primary-500)');
    });
  });
});
