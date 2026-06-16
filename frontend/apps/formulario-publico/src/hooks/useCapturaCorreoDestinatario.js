/**
 * Hook: useCapturaCorreoDestinatario
 *
 * Gestiona la intercepción del correo destinatario cuando el cliente/proveedor
 * accede al enlace de diligenciamiento por primera vez.
 *
 * Responsabilidad única: detectar si el acceso (identificado por token) aún
 * no tiene correo registrado y controlar la visibilidad del modal de captura.
 *
 * Flujo:
 *   1. Se detecta un ?token= en la URL.
 *   2. Se consulta al backend el ESTADO del correo vía GET /estado-correo
 *      (endpoint liviano — solo devuelve { correo_registrado: bool }).
 *   3. Si correo_registrado === false → mostrar modal.
 *   4. El usuario ingresa su correo → PATCH al backend → modal se cierra.
 *   5. Si ya tiene correo → modal nunca se abre (idempotente).
 *   6. En F5 / reactivación de pestaña → se re-verifica el servidor.
 *      El modal reaparece si el correo todavía no está registrado.
 *
 * Performance:
 *   Se usa api.verificarEstadoCorreo en lugar de api.resolverTokenDiligenciamiento.
 *   La diferencia es que el endpoint de estado solo hace 1 query simple contra
 *   accesos_manuales, sin cargar el snapshot completo del formulario (~10 JOINs).
 *
 * SRP: no conoce el formulario ni los otros hooks; solo sabe del correo del acceso.
 * DIP: depende de la abstracción `api`, no de la implementación de red directamente.
 */

import { useState, useCallback, useEffect } from 'react';
import { api } from '../services/api';

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Detecta el token en la URL sin modificar el historial del navegador.
 * Retorna null si no hay token.
 */
function _leerTokenDeUrl() {
  return new URLSearchParams(window.location.search).get('token') ?? null;
}

export function useCapturaCorreoDestinatario() {
  const [verificando, setVerificando]           = useState(() => !!_leerTokenDeUrl());
  const [correoRequerido, setCorreoRequerido]   = useState(false);
  const [tokenActivo,     setTokenActivo]       = useState(null);
  const [enviando,        setEnviando]          = useState(false);
  const [error,           setError]             = useState(null);

  // ── Detección inicial y re-verificación ──────────────────────────────────────
  // Usa el endpoint liviano /estado-correo que solo consulta 1 campo en BD.
  // Se ejecuta al montar y cada vez que la página vuelve a estar visible
  // (refresh, reapertura de tab, bfcache, etc.).
  // Garantiza que el modal siempre aparezca si el correo aún no está registrado.
  const _verificarCorreoDestinatario = useCallback(() => {
    const token = _leerTokenDeUrl();
    if (!token) return;

    // Guardar el token para reutilizarlo en el PATCH sin leer la URL de nuevo.
    setTokenActivo(token);

    api.verificarEstadoCorreo(token)
      .then(({ correo_registrado }) => {
        if (!correo_registrado) {
          setCorreoRequerido(true);
        }
      })
      .catch(() => {
        // Los errores de token (inválido/expirado) son manejados por useRecuperacionSesion.
        // Este hook solo necesita saber si el correo ya fue registrado; si el token
        // falla, simplemente no abrimos el modal (el otro hook se encarga del error).
      })
      .finally(() => {
        setVerificando(false);
      });
  }, []);

  useEffect(() => {
    // Verificar al montar
    _verificarCorreoDestinatario();

    // Listener para cuando el navegador recupera la página del cache (back-forward cache)
    // o después de un refresh. Se dispara incluso si se hace F5 en la misma pestaña.
    const handlePageShow = () => {
      _verificarCorreoDestinatario();
    };

    // Listener para cuando la página cambia de pestaña/ventana y vuelve a ser visible.
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        _verificarCorreoDestinatario();
      }
    };

    window.addEventListener('pageshow', handlePageShow);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('pageshow', handlePageShow);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [_verificarCorreoDestinatario]);

  // ── Registro del correo ──────────────────────────────────────────────────────
  const registrarCorreo = useCallback(async (correo) => {
    if (!tokenActivo || !correo || !REGEX_CORREO.test(correo)) return;

    setEnviando(true);
    setError(null);

    try {
      await api.actualizarCorreoPorToken(tokenActivo, correo);
      setCorreoRequerido(false);
    } catch (errorApi) {
      const mensaje = errorApi.code === 'ACCESO_EXPIRADO'
        ? 'El acceso ha expirado. Solicite un nuevo enlace al área responsable.'
        : 'No se pudo registrar el correo. Intente nuevamente.';
      setError(mensaje);
    } finally {
      setEnviando(false);
    }
  }, [tokenActivo]);

  // ── Interfaz pública ─────────────────────────────────────────────────────────
  return {
    verificando,
    correoRequerido,
    enviando,
    error,
    registrarCorreo,
  };
}
