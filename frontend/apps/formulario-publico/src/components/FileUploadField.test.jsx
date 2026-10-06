import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import FileUploadField from './FileUploadField';

// Mock HelpIcon since it imports texts that might be complex
vi.mock('./HelpPanel', () => ({
  HelpIcon: () => <span data-testid="help-icon" />
}));

describe('FileUploadField', () => {
  const defaultProps = {
    label: 'Test File',
    tipoDoc: 'cedula',
    documentos: {},
    onFileChange: vi.fn(),
    onRemove: vi.fn(),
    onOpenHelp: vi.fn(),
  };

  it('renders upload zone when no file is present', () => {
    render(<FileUploadField {...defaultProps} />);
    expect(screen.getByText(/haga clic para seleccionar/i)).toBeInTheDocument();
  });

  it('renders uploading state correctly', () => {
    render(<FileUploadField {...defaultProps} uploading={true} />);
    expect(screen.getByText(/Analizando con IA/i)).toBeInTheDocument();
  });

  it('renders file info when a file is uploaded', () => {
    const propsWithFile = {
      ...defaultProps,
      documentos: {
        cedula: { nombre_archivo: 'test.pdf', tamano: 2048 }
      }
    };
    render(<FileUploadField {...propsWithFile} />);
    expect(screen.getByText('test.pdf')).toBeInTheDocument();
    expect(screen.getByText('2.0 KB')).toBeInTheDocument();
  });

  it('calls onRemove when delete button is clicked', () => {
    const propsWithFile = {
      ...defaultProps,
      documentos: {
        cedula: { nombre_archivo: 'test.pdf' }
      }
    };
    render(<FileUploadField {...propsWithFile} />);
    const deleteBtn = screen.getByTitle('Eliminar');
    fireEvent.click(deleteBtn);
    expect(defaultProps.onRemove).toHaveBeenCalledWith('cedula');
  });

  it('disables delete button when eliminando is true', () => {
    const propsWithFile = {
      ...defaultProps,
      eliminando: true,
      documentos: {
        cedula: { nombre_archivo: 'test.pdf' }
      }
    };
    render(<FileUploadField {...propsWithFile} />);
    const deleteBtn = screen.getByTitle('Eliminar');
    expect(deleteBtn).toBeDisabled();
    expect(screen.getByText('⏳')).toBeInTheDocument();
  });

  it('renders error message when error is passed', () => {
    render(<FileUploadField {...defaultProps} error="El archivo es muy pesado" />);
    expect(screen.getByText('El archivo es muy pesado')).toBeInTheDocument();
  });

  it('renders hint when hint is passed', () => {
    render(<FileUploadField {...defaultProps} hint="Max 5MB" />);
    expect(screen.getByText('(Max 5MB)')).toBeInTheDocument();
  });

  it('calls onFileChange when file is selected via click', () => {
    const originalCreateElement = document.createElement.bind(document);
    const mockInput = {
      type: '',
      accept: '',
      click: vi.fn(),
    };
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tag, options) => {
      if (tag === 'input') return mockInput;
      return originalCreateElement(tag, options);
    });

    render(<FileUploadField {...defaultProps} />);
    const dropzone = screen.getByText(/haga clic para seleccionar/i).closest('.file-upload-zone');
    fireEvent.click(dropzone);

    expect(mockInput.click).toHaveBeenCalled();

    const testFile = new File(['dummy content'], 'test.png', { type: 'image/png' });
    
    // Simulate user selecting a file
    mockInput.onchange({ target: { files: [testFile] } });

    expect(defaultProps.onFileChange).toHaveBeenCalledWith('cedula', testFile);
    createElementSpy.mockRestore();
  });

  it('calls onFileChange when file is dropped', () => {
    render(<FileUploadField {...defaultProps} />);
    const dropzone = screen.getByText(/haga clic para seleccionar/i).closest('.file-upload-zone');
    
    const testFile = new File(['dummy content'], 'drop.pdf', { type: 'application/pdf' });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [testFile]
      }
    });

    expect(defaultProps.onFileChange).toHaveBeenCalledWith('cedula', testFile);
  });

  it('adds and removes dragover class on drag events', () => {
    render(<FileUploadField {...defaultProps} />);
    const dropzone = screen.getByText(/haga clic para seleccionar/i).closest('.file-upload-zone');
    
    fireEvent.dragOver(dropzone);
    expect(dropzone).toHaveClass('dragover');
    
    fireEvent.dragLeave(dropzone);
    expect(dropzone).not.toHaveClass('dragover');
  });

  it('ignores drop if no file is dropped', () => {
    defaultProps.onFileChange.mockClear();
    render(<FileUploadField {...defaultProps} />);
    const dropzone = screen.getByText(/haga clic para seleccionar/i).closest('.file-upload-zone');
    
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [] // No files
      }
    });

    expect(defaultProps.onFileChange).not.toHaveBeenCalled();
    expect(dropzone).not.toHaveClass('dragover');
  });
});
