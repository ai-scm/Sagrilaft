/**
 * Hook: useAlertasRazonSocial
 *
 * Gestiona el estado de alertas de inconsistencia entre la razón social
 * del formulario y la encontrada en cada documento adjunto.
 *
 * Responsabilidades:
 *  1. Almacenar la razón social extraída por IA de cada documento.
 *  2. Calcular reactivamente alertas cuando cambia formData.razon_social.
 *  3. Permitir descartar alertas individualmente.
 *  4. Limpiar la extracción si un documento es eliminado.
 *
 * SRP: única responsabilidad — producir la lista de alertas de nombre activas.
 * DRY: la normalización está centralizada en normalizarRazonSocial (espejo del
 *      backend services/alertas/normalizador_nombre.py).
 *
 * La normalización en JS replica la lógica del backend para que la comparación
 * en tiempo real (mientras el usuario escribe) sea consistente con el backend.
 */

import { useCallback, useState } from 'react';

// ── Nombres legibles por tipo de documento (lenguaje ubícuo) ─────────────────

const NOMBRES_DOCUMENTOS = {
  certificado_existencia: 'Certificado de Existencia y Representación Legal',
  rut:                    'RUT (Registro Único Tributario)',
  estados_financieros:    'Estados Financieros',
  referencias_bancarias:  'Referencias Bancarias',
};

const SECCIONES_REFERENCIA = {
  certificado_existencia: 'NOMBRE, IDENTIFICACIÓN Y DOMICILIO → Razón social',
  rut:                    'IDENTIFICACIÓN → campo 35. Razón social',
  estados_financieros:    'Encabezado del documento (razón social del emisor)',
  referencias_bancarias:  'Nombre del titular de la cuenta',
};

// ── Normalización (espejo de backend/services/alertas/normalizador_nombre.py) ─

const SIGLAS_SOCIETARIAS = [
  [/SOCIEDAD POR ACCIONES SIMPLIFICADA/g, 'SAS'],
  [/SOCIEDAD ANONIMA SIMPLIFICADA/g,      'SAS'],
  [/SOCIEDAD DE RESPONSABILIDAD LIMITADA/g, 'LTDA'],
  [/EMPRESA UNIPERSONAL/g,                'EU'],
  [/SOCIEDAD ANONIMA/g,                   'SA'],
  [/SOCIEDAD EN COMANDITA POR ACCIONES/g, 'SCA'],
  [/SOCIEDAD EN COMANDITA SIMPLE/g,       'SCS'],
  [/S\.A\.S\.?/g,  'SAS'],
  [/S\.A\.?/g,     'SA'],
  [/LTDA\.?/g,     'LTDA'],
  [/LIMITADA\.?/g, 'LTDA'],
  [/E\.U\.?/g,     'EU'],
  [/S\.R\.L\.?/g,  'SRL'],
  [/S\.C\.A\.?/g,  'SCA'],
  [/S\.C\.S\.?/g,  'SCS'],
  [/E\.S\.P\.?/g,  'ESP'],
  [/CÍA\.?/g,      'CIA'],
  [/CIA\.?/g,      'CIA'],
  [/CO\.?/g,       'CO'],
];

function normalizarRazonSocial(valor) {
  if (!valor) return '';

  // 1. Quitar diacríticos
  let texto = valor
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  // 2. Mayúsculas
  texto = texto.toUpperCase();

  // 3. Normalizar siglas societarias (primero formas largas)
  for (const [patron, canonica] of SIGLAS_SOCIETARIAS) {
    texto = texto.replace(patron, canonica);
  }

  // 4. Eliminar puntos residuales
  texto = texto.replace(/\./g, '');

  // 5. Colapsar espacios
  texto = texto.replace(/\s+/g, ' ').trim();

  return texto;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * @returns {{
 *   registrarExtraccion: (tipoDoc: string, razonSocialExtraida: string) => void,
 *   calcularAlertas:     (razonSocialFormulario: string) => AlertaInconsistencia[],
 *   descartarAlerta:     (tipoDoc: string) => void,
 *   limpiarExtraccion:   (tipoDoc: string) => void,
 * }}
 *
 * @typedef {{
 *   tipoDoc:         string,
 *   nombreDocumento: string,
 *   seccionReferencia: string,
 *   valorFormulario: string,
 *   valorDocumento:  string,
 * }} AlertaInconsistencia
 */
export function useAlertasRazonSocial() {
  // Razón social extraída por IA, indexada por tipo de documento
  const [razonSocialPorDocumento, setRazonSocialPorDocumento] = useState({});

  // Tipos de documento cuya alerta fue descartada manualmente por el usuario
  const [alertasDescartadas, setAlertasDescartadas] = useState(new Set());

  /**
   * Registra la razón social extraída de un documento recién subido.
   * Reactiva la alerta si el mismo documento es reemplazado.
   */
  const registrarExtraccion = useCallback((tipoDoc, razonSocialExtraida) => {
    if (!razonSocialExtraida) return;
    setRazonSocialPorDocumento(prev => ({ ...prev, [tipoDoc]: razonSocialExtraida }));
    // Reactivar alerta del documento ante una nueva carga
    setAlertasDescartadas(prev => {
      const siguiente = new Set(prev);
      siguiente.delete(tipoDoc);
      return siguiente;
    });
  }, []);

  /**
   * Calcula las alertas activas comparando cada extracción con la razón social
   * actual del formulario. Llamar en cada render pasando formData.razon_social.
   *
   * @param {string} razonSocialFormulario - Valor actual del campo razon_social.
   * @returns {AlertaInconsistencia[]}
   */
  const calcularAlertas = useCallback(
    (razonSocialFormulario) => {
      if (!razonSocialFormulario) return [];

      const normForm = normalizarRazonSocial(razonSocialFormulario);

      return Object.entries(razonSocialPorDocumento)
        .filter(([tipoDoc]) => !alertasDescartadas.has(tipoDoc))
        .map(([tipoDoc, razonSocialDoc]) => {
          const normDoc = normalizarRazonSocial(razonSocialDoc);
          if (!normDoc || normForm === normDoc) return null;
          return {
            tipoDoc,
            nombreDocumento:  NOMBRES_DOCUMENTOS[tipoDoc]    || tipoDoc,
            seccionReferencia: SECCIONES_REFERENCIA[tipoDoc] || '',
            valorFormulario:  razonSocialFormulario,
            valorDocumento:   razonSocialDoc,
          };
        })
        .filter(Boolean);
    },
    [razonSocialPorDocumento, alertasDescartadas],
  );

  /**
   * Marca una alerta como descartada. No borra la extracción almacenada:
   * si el usuario corrige el nombre, la alerta desaparece sola por recálculo.
   */
  const descartarAlerta = useCallback((tipoDoc) => {
    setAlertasDescartadas(prev => new Set([...prev, tipoDoc]));
  }, []);

  /**
   * Elimina la extracción de un documento (cuando el documento es borrado).
   */
  const limpiarExtraccion = useCallback((tipoDoc) => {
    setRazonSocialPorDocumento(prev => {
      const siguiente = { ...prev };
      delete siguiente[tipoDoc];
      return siguiente;
    });
    setAlertasDescartadas(prev => {
      const siguiente = new Set(prev);
      siguiente.delete(tipoDoc);
      return siguiente;
    });
  }, []);

  return {
    registrarExtraccion,
    calcularAlertas,
    descartarAlerta,
    limpiarExtraccion,
  };
}
