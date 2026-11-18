import { Tags } from 'aws-cdk-lib';
import { IConstruct } from 'constructs';

/**
 * Criterio único de etiquetado de SAGRILAFT en AWS.
 *
 * - Project:     sistema al que pertenece el recurso (siempre `sagrilaft`).
 * - Environment: ambiente (`staging`, `prod`, ...).
 * - Component:   función del recurso dentro del sistema (lista cerrada abajo).
 * - ManagedBy:   cómo se administra; todo lo que crea este stack es `cdk`.
 *
 * Los recursos compartidos con otros proyectos de la cuenta (certificado comodín,
 * zona `ia.blend360.com`, identidad SES, rol OIDC de GitHub) nunca se etiquetan
 * como SAGRILAFT: no pertenecen a este stack.
 *
 * Criterio completo y recursos fuera de CDK: docs/produccion/configuracion/ETIQUETADO_AWS.md
 */
export const ETIQUETA_PROYECTO = 'Project';
export const ETIQUETA_AMBIENTE = 'Environment';
export const ETIQUETA_COMPONENTE = 'Component';
export const ETIQUETA_ADMINISTRACION = 'ManagedBy';

export const PROYECTO = 'sagrilaft';
export const ADMINISTRADO_POR_CDK = 'cdk';

export const COMPONENTES = [
  'red',
  'balanceador',
  'cortafuegos-web',
  'plataforma-contenedores',
  'backend',
  'formulario-publico',
  'portal-interno',
  'keycloak',
  'listas-worker',
  'migraciones',
  'base-datos',
  'almacenamiento',
  'secretos',
  'configuracion',
  'notificaciones',
  'observabilidad',
] as const;

export type Componente = (typeof COMPONENTES)[number];

/** Etiquetas comunes a todo el stack. */
export function etiquetarSistema(alcance: IConstruct, ambiente: string): void {
  Tags.of(alcance).add(ETIQUETA_PROYECTO, PROYECTO);
  Tags.of(alcance).add(ETIQUETA_AMBIENTE, ambiente);
  Tags.of(alcance).add(ETIQUETA_ADMINISTRACION, ADMINISTRADO_POR_CDK);
}

/**
 * Marca la función de uno o varios constructs y de todo lo que contienen.
 * Si un recurso queda bajo dos alcances etiquetados, gana el más cercano
 * (p. ej. el servicio backend dentro del construct ECS).
 */
export function etiquetarComponente(componente: Componente, ...alcances: IConstruct[]): void {
  for (const alcance of alcances) {
    Tags.of(alcance).add(ETIQUETA_COMPONENTE, componente);
  }
}
