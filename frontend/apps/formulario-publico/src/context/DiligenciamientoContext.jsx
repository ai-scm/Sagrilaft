import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import {
  leerBorradorDeStorage,
  eliminarBorradorDeStorage,
  borradorEsFormularioEnviado,
} from '../utils/borradorStorage';

const DiligenciamientoContext = createContext();

export function DiligenciamientoProvider({ children }) {
  const [sesionActiva, setSesionActiva] = useState(false);
  const [snapshotInicial, setSnapshotInicial] = useState(null);
  const [borradorLocal, setBorradorLocal] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const credencialesRef = useRef(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    
    if (token) {
      api.resolverTokenDiligenciamiento(token)
        .then(formulario => {
          credencialesRef.current = { token_diligenciamiento: token };
          setSnapshotInicial(formulario);
          setSesionActiva(true);
          window.history.replaceState({}, '', window.location.pathname);
        })
        .catch(err => {
          if (err.code === 'ACCESO_EXPIRADO') {
            setError('El enlace ha expirado. Ingrese su código de petición y PIN, o solicite un nuevo enlace.');
          } else {
            setError('Enlace inválido. Por favor, ingrese sus credenciales.');
          }
        })
        .finally(() => setCargando(false));
      return;
    }

    // Si no hay token, revisar si hay borrador local
    const borrador = leerBorradorDeStorage();
    if (borrador) {
      if (borradorEsFormularioEnviado(borrador)) {
        eliminarBorradorDeStorage();
      } else if (!borrador.formularioId && !borrador.codigoPeticion) {
        // Borrador puramente local sin sincronizar. Restaurar directo.
        setSnapshotInicial(borrador);
        setSesionActiva(true);
      } else {
        setBorradorLocal(borrador);
      }
    }
    
    setCargando(false);
  }, []);

  const ingresarConCredenciales = async (codigoPeticion, pin) => {
    setCargando(true);
    setError(null);
    try {
      const formulario = await api.recuperarSesionPorAcceso(codigoPeticion, pin);
      credencialesRef.current = { codigo_peticion: codigoPeticion, pin };
      
      // Preservar temporalmente el borrador local en el payload para que 
      // useRecuperacionSesion pueda hidratar los datos extraídos por IA
      // antes de que el borrador sea destruido de la memoria.
      formulario._borradorLocalPrecedente = borradorLocal;

      setSnapshotInicial(formulario);
      setSesionActiva(true);
      eliminarBorradorDeStorage();
      setBorradorLocal(null);
    } catch (err) {
      if (err.code === 'CREDENCIALES_INVALIDAS') setError('Código de petición o PIN incorrecto. Verifique los datos.');
      else if (err.code === 'FORMULARIO_YA_ENVIADO') setError('Este formulario ya fue enviado y no puede recuperarse.');
      else if (err.code === 'ACCESO_EXPIRADO') setError('El acceso ha expirado. Solicite un nuevo enlace al área responsable.');
      else setError('Error al conectar con el servidor. Intente nuevamente.');
    } finally {
      setCargando(false);
    }
  };

  const cerrarSesion = (mensajeError) => {
    setSesionActiva(false);
    setSnapshotInicial(null);
    setError(mensajeError || 'Su sesión ha expirado.');
  };

  const descartarBorrador = () => {
    eliminarBorradorDeStorage();
    setBorradorLocal(null);
    setError(null);
  };

  return (
    <DiligenciamientoContext.Provider value={{
      sesionActiva, 
      snapshotInicial, 
      borradorLocal,
      cargando, 
      error, 
      ingresarConCredenciales, 
      cerrarSesion,
      descartarBorrador,
      credencialesRef
    }}>
      {children}
    </DiligenciamientoContext.Provider>
  );
}

export const useDiligenciamiento = () => useContext(DiligenciamientoContext);
