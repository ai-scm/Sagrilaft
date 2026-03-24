import { useState } from 'react';
import helpTexts from '../data/helpTexts';

/**
 * Panel lateral de ayuda que se despliega al hacer click en el ícono "?".
 */
export default function HelpPanel({ fieldKey, onClose }) {
  const help = helpTexts[fieldKey];

  if (!help) return null;

  return (
    <>
      <div className="help-panel-overlay" onClick={onClose} />
      <div className="help-panel">
        <div className="help-panel-header">
          <h3>ℹ️ {help.titulo}</h3>
          <button className="help-panel-close" onClick={onClose}>✕</button>
        </div>
        <div className="help-panel-content">
          <p>{help.descripcion}</p>
          {help.ejemplo && (
            <div className="help-example">
              <strong>Ejemplo:</strong> {help.ejemplo}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/**
 * Ícono de ayuda "?" que aparece al lado de cada campo.
 */
export function HelpIcon({ fieldKey, onOpenHelp }) {
  return (
    <span
      className="help-icon"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onOpenHelp(fieldKey);
      }}
      title="Ayuda"
    >
      ?
    </span>
  );
}
