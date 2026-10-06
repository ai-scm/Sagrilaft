import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import FirmaRepresentanteLegal from './FirmaRepresentanteLegal';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    obtenerFechaServidor: vi.fn()
  }
}));

describe('FirmaRepresentanteLegal', () => {
  const defaultProps = {
    formData: {},
    onChange: vi.fn(),
    onOpenHelp: vi.fn(),
    errors: {}
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly with empty formData', () => {
    render(<FirmaRepresentanteLegal {...defaultProps} />);
    expect(screen.getByText('Firma del Representante Legal')).toBeInTheDocument();
    expect(screen.getByText('Usar fecha del servidor')).toBeInTheDocument();
  });

  it('fetches server date and calls onChange 3 times', async () => {
    api.obtenerFechaServidor.mockResolvedValueOnce({ dia: 20, mes: 'Agosto', year: 2026 });
    render(<FirmaRepresentanteLegal {...defaultProps} />);
    
    const serverBtn = screen.getByText('Usar fecha del servidor');
    fireEvent.click(serverBtn);

    expect(screen.getByText('Cargando fecha...')).toBeInTheDocument();

    await waitFor(() => {
      expect(api.obtenerFechaServidor).toHaveBeenCalled();
      expect(defaultProps.onChange).toHaveBeenCalledWith(
        expect.objectContaining({ target: expect.objectContaining({ name: 'dia_firma', value: '20' }) })
      );
      expect(defaultProps.onChange).toHaveBeenCalledWith(
        expect.objectContaining({ target: expect.objectContaining({ name: 'mes_firma', value: 'Agosto' }) })
      );
      expect(defaultProps.onChange).toHaveBeenCalledWith(
        expect.objectContaining({ target: expect.objectContaining({ name: 'year_firma', value: '2026' }) })
      );
    });
  });

  it('clears date when Limpiar fecha is clicked', () => {
    const props = {
      ...defaultProps,
      formData: { dia_firma: '15', mes_firma: 'Enero', year_firma: '2025' }
    };
    render(<FirmaRepresentanteLegal {...props} />);
    
    const clearBtn = screen.getByText('Limpiar fecha');
    fireEvent.click(clearBtn);

    expect(defaultProps.onChange).toHaveBeenCalledWith(
      expect.objectContaining({ target: expect.objectContaining({ name: 'dia_firma', value: '' }) })
    );
  });

  it('shows error messages for invalid fields', () => {
    const props = {
      ...defaultProps,
      errors: { dia_firma: 'Día inválido' }
    };
    render(<FirmaRepresentanteLegal {...props} />);
    expect(screen.getByText('Día inválido')).toBeInTheDocument();
  });



  it('updates narrative text dynamically with values from formData', () => {
    const propsWithData = {
      ...defaultProps,
      formData: {
        dia_firma: '25',
        mes_firma: '10',
        year_firma: '2026',
        ciudad_firma: 'Medellín'
      }
    };
    render(<FirmaRepresentanteLegal {...propsWithData} />);
    
    const narrative = screen.getByText(/En constancia de haber leído y acatado/i);
    expect(narrative).toHaveTextContent('25');
    expect(narrative).toHaveTextContent(/octubre/i);
    expect(narrative).toHaveTextContent('2026');
    expect(narrative).toHaveTextContent('Medellín');
  });
});
