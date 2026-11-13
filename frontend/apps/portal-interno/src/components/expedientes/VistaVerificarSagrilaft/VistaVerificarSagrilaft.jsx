/**
 * VistaVerificarSagrilaft — Pestaña independiente de "Verificar SAGRILAFT".
 *
 * Permite buscar un expediente y, sobre el seleccionado, ejecutar la misma
 * consulta de listas cautelares (OFAC) que antes se abría desde un botón
 * dentro del detalle del expediente.
 */

import { useMemo, useState } from 'react';
import Spinner from '@shared/components/ui/Spinner';
import Alert from '@shared/components/ui/Alert';
import InputBusqueda from '../../ui/InputBusqueda';
import { estilosBandeja } from '../../ui/listaStyles';
import useExpedientes from '../../../hooks/useExpedientes';
import { useExpedienteDetalle } from '../../../hooks/useExpedienteDetalle';
import TarjetaExpediente from '../TarjetaExpediente';
import ConsultasListas from '../DetalleExpediente/ConsultasListas';

const s = {
  ...estilosBandeja,
  btnVolver: {
    alignSelf:    'flex-start',
    padding:      '6px 14px',
    background:   'transparent',
    color:        'var(--primary-600, #2563eb)',
    border:       '1.5px solid var(--primary-200, #bfdbfe)',
    borderRadius: 'var(--radius-sm, 6px)',
    fontSize:     '0.8rem',
    fontWeight:   '600',
    cursor:       'pointer',
  },
  tituloSeleccion: {
    fontSize:   '1.1rem',
    fontWeight: '700',
    color:      'var(--gray-900, #0f172a)',
    margin:     0,
  },
};

export default function VistaVerificarSagrilaft() {
  const [busqueda, setBusqueda] = useState('');
  const [seleccion, setSeleccion] = useState(null);

  const { expedientes, cargando, error, busquedaDebounced } = useExpedientes({ filtroTipo: '', busqueda });
  const { expediente, cargando: cargandoDetalle, error: errorDetalle } = useExpedienteDetalle(seleccion?.formulario_id);
  // Referencia estable: evita que ConsultasListas reciba un objeto "nuevo" en
  // cada render (y con él, pierda la memoización de sus hijos) cuando en
  // realidad el expediente no cambió.
  const expedienteConsulta = useMemo(
    () => expediente && seleccion ? { ...expediente, id: seleccion.formulario_id } : null,
    [expediente, seleccion],
  );

  if (seleccion) {
    return (
      <div style={s.contenedor}>
        <button type="button" style={s.btnVolver} onClick={() => setSeleccion(null)}>
          ← Volver a la búsqueda
        </button>
        <h2 style={s.tituloSeleccion}>{seleccion.razon_social ?? '(Sin razón social)'}</h2>
        {cargandoDetalle && <Spinner texto="Cargando expediente…" style={{ padding: '60px 0' }} />}
        {errorDetalle && <Alert mensaje={errorDetalle} style={{ margin: '24px 0' }} />}
        {!cargandoDetalle && expedienteConsulta && (
          <ConsultasListas expediente={expedienteConsulta} />
        )}
      </div>
    );
  }

  const terminoBusqueda = busquedaDebounced.trim().toLowerCase();
  const expedientesFiltrados = expedientes.filter(e =>
    !terminoBusqueda ||
    (e.razon_social ?? '').toLowerCase().includes(terminoBusqueda) ||
    (e.codigo_peticion ?? '').toLowerCase().includes(terminoBusqueda));

  return (
    <div style={s.contenedor}>
      <div style={s.barraFiltros}>
        <InputBusqueda
          valor={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por razón social o código…"
        />
      </div>

      {error && <Alert mensaje={error} />}
      {cargando && !error && <Spinner texto="Cargando formularios…" />}
      {!cargando && !error && expedientesFiltrados.length === 0 && (
        <div style={s.estadoVacio}>Ningún formulario coincide con la búsqueda.</div>
      )}
      {!cargando && expedientesFiltrados.map(e => (
        <TarjetaExpediente key={e.formulario_id} expediente={e} onClick={setSeleccion} />
      ))}
    </div>
  );
}
