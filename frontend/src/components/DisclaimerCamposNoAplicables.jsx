import { useCallback } from 'react';
import { usePersistenciaAviso } from '../hooks/usePersistenciaAviso';

const CLAVE_SESION = 'sagrilaft_aviso_campos_na_colapsado';

export default function DisclaimerCamposNoAplicables() {
  const [colapsado, setColapsado] = usePersistenciaAviso(CLAVE_SESION, false);

  const alternarColapso = useCallback(() => {
    setColapsado(prev => !prev);
  }, [setColapsado]);

  return (
    <div
      className={`aviso-campos-na${colapsado ? ' aviso-campos-na--colapsado' : ''}`}
      role="note"
      aria-label="Instrucción para campos que no aplican"
    >
      <div className="aviso-campos-na__encabezado">
        <span className="aviso-campos-na__icono" aria-hidden="true">ℹ</span>

        {colapsado && (
          <span className="aviso-campos-na__resumen">
            Instrucción de diligenciamiento
          </span>
        )}

        <button
          type="button"
          className="aviso-campos-na__toggle"
          onClick={alternarColapso}
          aria-expanded={!colapsado}
          aria-controls="aviso-campos-na-contenido"
        >
          {colapsado ? 'Ver instrucción ▾' : 'Ocultar ▴'}
        </button>
      </div>

      <div
        id="aviso-campos-na-contenido"
        className="aviso-campos-na__contenido"
        hidden={colapsado}
      >
        <p className="aviso-campos-na__mensaje">
          Si alguna información <strong>no aplica</strong>, deberá diligenciar{' '}
          <span className="aviso-campos-na__etiqueta-na" aria-label="la sigla N A">NA</span>{' '}
          en el campo correspondiente.
        </p>
      </div>
    </div>
  );
}
