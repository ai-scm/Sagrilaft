import { FileBarChart, FileText } from 'lucide-react';
import DocumentoResumenCard from './DocumentoResumenCard';

export default function ResumenExpediente({ formularioId, pdfFormulario, reporteFinal }) {
  if (!pdfFormulario && !reporteFinal) return null;

  return (
    <section className="section-block">
      <div className="section-header">
        <h2 className="section-title">Resumen del Expediente</h2>
      </div>
      <div className="summary-cards">
        {pdfFormulario && (
          <DocumentoResumenCard
            documento={pdfFormulario}
            formularioId={formularioId}
            titulo="Formulario Oficial SAGRILAFT"
            icono={(
              <div className="card-icon">
                <FileText className="text-blue-500" size={24} />
              </div>
            )}
          />
        )}
        {reporteFinal && (
          <DocumentoResumenCard
            documento={reporteFinal}
            formularioId={formularioId}
            titulo="Reporte Final de Cierre"
            botonClassName="btn-outline"
            tituloDescarga="Descargar Reporte"
            icono={(
              <div className="card-icon green">
                <FileBarChart className="text-green-500" size={24} />
              </div>
            )}
          />
        )}
      </div>
    </section>
  );
}
