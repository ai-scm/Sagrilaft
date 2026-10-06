import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FormularioSagrilaft from './FormularioSagrilaft';
import * as formHooks from '../hooks/formulario';
import * as radHooks from '../hooks/radicacion';

vi.mock('../hooks/formulario', () => ({
  useFormulario: vi.fn()
}));

vi.mock('../hooks/radicacion', () => ({
  useDisclaimerRadicacion: vi.fn(),
  DISCLAIMER_RADICACION: { badge: '✅', puntos: [] }
}));

// Mock the actual steps to keep tests isolated and fast
vi.mock('./pasos/PasoDocumentos', () => ({ default: () => <div data-testid="paso-documentos">Paso 1</div> }));
vi.mock('./pasos/PasoInfoBasica', () => ({ default: () => <div data-testid="paso-info-basica">Paso 2</div> }));
vi.mock('./SubmittedView', () => ({ default: () => <div data-testid="submitted-view">Enviado</div> }));

describe('FormularioSagrilaft', () => {
  const defaultMockFormulario = {
    step: 1,
    formData: {},
    errors: {},
    helpField: null,
    setHelpField: vi.fn(),
    pasosVisibles: [1, 2, 3, 4, 5, 6, 7, 8],
    estadoFormulario: 'NUEVO',
    camposACorregir: [],
    formDataOriginal: {},
    tablasOriginales: {},
    documentos: {},
    uploadingDoc: {},
    eliminandoDoc: {},
    estadoConfirmacion: { visible: false },
    juntaDirectiva: [],
    accionistas: [],
    beneficiarios: [],
    referenciasComerciales: [],
    referenciasBancarias: [],
    infoBancariaPagos: [],
    submitted: false,
    handleChange: vi.fn(),
    handleNext: vi.fn(),
    handlePrev: vi.fn(),
    handleSubmit: vi.fn(),
    irAPasoCorreccion: vi.fn(),
    alertasRazonSocial: [],
    alertasNit: [],
    alertasNombreRepresentante: [],
    alertasNumeroDocRepresentante: [],
    alertasDireccion: [],
    hayAlertasActivas: false
  };

  const defaultMockRadicacion = {
    aceptado: false,
    mensajeError: null,
    setAceptado: vi.fn(),
    validarDisclaimer: vi.fn().mockReturnValue(false)
  };

  beforeEach(() => {
    vi.mocked(formHooks.useFormulario).mockReturnValue(defaultMockFormulario);
    vi.mocked(radHooks.useDisclaimerRadicacion).mockReturnValue(defaultMockRadicacion);
  });

  it('renders header and step 1 initially', () => {
    render(<FormularioSagrilaft />);
    
    expect(screen.getByText(/FORMULARIO DE VINCULACIÓN/i)).toBeInTheDocument();
    expect(screen.getByTestId('paso-documentos')).toBeInTheDocument();
  });

  it('renders Step 2 when step is 2', () => {
    vi.mocked(formHooks.useFormulario).mockReturnValue({ ...defaultMockFormulario, step: 2 });
    render(<FormularioSagrilaft />);
    expect(screen.getByTestId('paso-info-basica')).toBeInTheDocument();
    expect(screen.queryByTestId('paso-documentos')).not.toBeInTheDocument();
  });

  it('renders SubmittedView when submitted is true', () => {
    vi.mocked(formHooks.useFormulario).mockReturnValue({ ...defaultMockFormulario, submitted: true });
    render(<FormularioSagrilaft />);
    expect(screen.getByTestId('submitted-view')).toBeInTheDocument();
    expect(screen.queryByText(/FORMULARIO DE VINCULACIÓN/i)).not.toBeInTheDocument();
  });

  it('blocks final submit when disclaimer is not accepted (step 8)', async () => {
    vi.mocked(formHooks.useFormulario).mockReturnValue({ ...defaultMockFormulario, step: 8 });
    const mockValidar = vi.fn().mockReturnValue(false);
    vi.mocked(radHooks.useDisclaimerRadicacion).mockReturnValue({ ...defaultMockRadicacion, validarDisclaimer: mockValidar });
    
    render(<FormularioSagrilaft />);
    const submitBtn = screen.getByText(/Radicar Formulario/i);
    fireEvent.click(submitBtn);
    
    expect(defaultMockFormulario.handleSubmit).not.toHaveBeenCalled();
  });

  it('allows final submit when disclaimer is accepted (step 8)', async () => {
    vi.mocked(formHooks.useFormulario).mockReturnValue({ ...defaultMockFormulario, step: 8 });
    const mockValidar = vi.fn().mockReturnValue(true);
    vi.mocked(radHooks.useDisclaimerRadicacion).mockReturnValue({ ...defaultMockRadicacion, aceptado: true, validarDisclaimer: mockValidar });
    
    render(<FormularioSagrilaft />);
    const submitBtn = screen.getByText(/Radicar Formulario/i);
    fireEvent.click(submitBtn);
    
    expect(mockValidar).toHaveBeenCalled();
    expect(defaultMockFormulario.handleSubmit).toHaveBeenCalled();
  });

  it('blocks navigation to next step while IA is analyzing (uploadingDoc)', () => {
    vi.mocked(formHooks.useFormulario).mockReturnValue({ ...defaultMockFormulario, uploadingDoc: { cedula: true } });
    render(<FormularioSagrilaft />);
    const nextBtn = screen.getByText(/Siguiente/i);
    expect(nextBtn).toBeDisabled();
  });
});
