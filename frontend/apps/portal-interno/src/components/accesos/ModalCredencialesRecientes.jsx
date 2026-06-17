import { useState, useRef, useEffect } from 'react';
import { formatearFechaLarga, ETIQUETA_TIPO_CONTRAPARTE } from '../../config/constantes';
import { ESTILOS } from './CrearAccesoManualStyles';

const estiloFondo = {
  position: 'fixed',
  top: 0,
  left: 0,
  width: '100%',
  height: '100%',
  backgroundColor: 'rgba(0, 0, 0, 0.5)',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 1000,
  padding: '20px',
  boxSizing: 'border-box'
};

const estiloModalContenedor = {
  width: '100%',
  maxWidth: '560px',
  maxHeight: '90vh',
  overflowY: 'auto',
  borderRadius: 'var(--radius-lg, 12px)',
};

function ItemCredencial({ label, valor, monospace = true }) {
  const estiloValor = monospace
    ? ESTILOS.credencialValor
    : { ...ESTILOS.credencialValor, fontFamily: 'inherit', letterSpacing: 0 };
  return (
    <div style={ESTILOS.credencial}>
      <span style={ESTILOS.credencialLabel}>{label}</span>
      <span style={estiloValor}>{valor}</span>
    </div>
  );
}

export default function ModalCredencialesRecientes({ credenciales, onClose }) {
  const [copiado, setCopiado] = useState(false);
  const temporizadorRef = useRef(null);

  useEffect(() => () => clearTimeout(temporizadorRef.current), []);

  if (!credenciales) return null;

  const handleCopiarEnlace = () => {
    navigator.clipboard.writeText(credenciales.enlace_diligenciamiento).then(() => {
      setCopiado(true);
      clearTimeout(temporizadorRef.current);
      temporizadorRef.current = setTimeout(() => setCopiado(false), 2500);
    });
  };

  return (
    <div style={estiloFondo} onClick={onClose}>
      <div style={estiloModalContenedor} onClick={(e) => e.stopPropagation()}>
        <div style={ESTILOS.panelExito}>
          <div style={ESTILOS.encabezadoExito}>
            <p style={ESTILOS.tituloExito}>Credenciales del Acceso</p>
            <p style={ESTILOS.subtituloExito}>
              {credenciales.razon_social} · {ETIQUETA_TIPO_CONTRAPARTE[credenciales.tipo_contraparte] ?? credenciales.tipo_contraparte}
            </p>
          </div>

          <div style={ESTILOS.cuerpoExito}>
            <div style={ESTILOS.advertenciaPIN}>
              <strong>Aviso:</strong> Estás viendo estas credenciales porque fueron generadas recientemente (ventana de gracia).
              Una vez expirada esta ventana, el PIN no podrá recuperarse.
            </div>

            <ItemCredencial label="Código de petición" valor={credenciales.codigo_peticion} />
            <ItemCredencial label="PIN de acceso"       valor={credenciales.pin} />
            {credenciales.correo_destinatario && <ItemCredencial label="Destinatario" valor={credenciales.correo_destinatario} monospace={false} />}
            <ItemCredencial label="Válido hasta"        valor={formatearFechaLarga(credenciales.expires_at)} monospace={false} />

            <div style={ESTILOS.enlaceBox}>
              <p style={ESTILOS.enlaceLabel}>Enlace de diligenciamiento</p>
              <p style={ESTILOS.enlaceTexto}>{credenciales.enlace_diligenciamiento}</p>
              <button style={ESTILOS.btnCopiar} onClick={handleCopiarEnlace} type="button">
                {copiado ? 'Copiado' : 'Copiar enlace'}
              </button>
            </div>

            <button style={ESTILOS.btnPrincipal} onClick={onClose} type="button">
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
