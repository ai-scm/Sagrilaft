"""
Generador de fichas HTML para comparación de campos complejos.

Responsabilidades:
  - Generar fichas HTML para arreglos de objetos.
  - Generar tags de arreglos simples (badges).
  - Formateo de valores según tipo de campo.
  - Uso de configuración inyectable de campos.
"""

import json
from html import escape
from typing import Any, Dict, List, Optional

from services.expedientes.configuracion_campos_complejos import (
    ConfiguracionCamposComplejos,
)


# Instancia global de configuración (puede ser inyectada en testing)
_CONFIGURACION_GLOBAL = ConfiguracionCamposComplejos.por_defecto()


def obtener_configuracion_comparador(nombre_campo: str) -> Dict[str, Any]:
    """
    Obtiene configuración de campos para un tipo de registro complejo.
    
    Nota: Esta función es un wrapper para compatibilidad con código existente.
    En código nuevo, preferir usar ConfiguracionCamposComplejos directamente.
    """
    return _CONFIGURACION_GLOBAL.obtener(nombre_campo)


def es_campo_complejo(nombre_campo: str) -> bool:
    """
    Determina si un campo requiere visualización como fichas o arreglo.
    
    Nota: Esta función es un wrapper para compatibilidad con código existente.
    En código nuevo, preferir usar ConfiguracionCamposComplejos.es_campo_complejo().
    """
    return _CONFIGURACION_GLOBAL.es_campo_complejo(nombre_campo)


def parsear_arreglo_valores(valor: Any) -> list:
    """Parsea un valor a arreglo, manejando strings JSON y errores."""
    if not valor or valor == "Sin información":
        return []
    if isinstance(valor, list):
        return valor
    if isinstance(valor, str):
        try:
            arregloParsado = json.loads(valor)
            if isinstance(arregloParsado, list):
                return arregloParsado
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def son_valores_iguales(valor_a: Any, valor_b: Any) -> bool:
    """Comprueba si dos valores son iguales tras normalización."""
    str_a = (str(valor_a) if valor_a is not None else '').strip().lower()
    str_b = (str(valor_b) if valor_b is not None else '').strip().lower()
    return str_a == str_b


def formatear_valor_campo(valor: Any, clave: str) -> str:
    """Formatea un valor según el tipo de campo."""
    if valor is None or valor == '':
        return ''
    if clave == 'porcentaje':
        try:
            numero = float(valor)
            return f'{numero}%'
        except (ValueError, TypeError):
            return str(valor)
    return str(valor)


def generar_html_arreglo_simple(
    valoresAntes: list,
    valoresDespues: list,
    configuracion: Dict[str, Any],
) -> str:
    """Genera HTML para comparación de arreglos simples (lista de strings)."""
    conjuntoAntes = set(valoresAntes)
    conjuntoDespues = set(valoresDespues)

    valoresEliminados = [v for v in valoresAntes if v not in conjuntoDespues]
    valoresNuevos = [v for v in valoresDespues if v not in conjuntoAntes]
    valoresIguales = [v for v in valoresAntes if v in conjuntoDespues]

    etiquetasValores = configuracion.get('etiquetasValores', {})

    html = []

    if valoresEliminados:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #dc2626; margin-bottom: 6px; font-size: 11px;">Eliminados:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresEliminados:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #fff7ed; border: 1px solid #fed7aa; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #7c2d12;">{escape(etiqueta)}</span>')
        html.append('</div></div>')

    if valoresIguales:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #666; margin-bottom: 6px; font-size: 11px;">Sin cambios:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresIguales:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #475569;">{escape(etiqueta)}</span>')
        html.append('</div></div>')

    if valoresNuevos:
        html.append('<div style="margin-bottom: 12px;">')
        html.append('<div style="font-weight: bold; color: #16a34a; margin-bottom: 6px; font-size: 11px;">Agregados:</div>')
        html.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">')
        for valor in valoresNuevos:
            etiqueta = etiquetasValores.get(valor, valor)
            html.append(f'<span style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 3px; padding: 4px 8px; font-size: 10px; color: #166534;">{escape(etiqueta)}</span>')
        html.append('</div></div>')

    return ''.join(html)


def generar_fichas_registro_comparadas(
    nombre_campo: str,
    valor_anterior: Any,
    valor_corregido: Any,
    config: Optional[ConfiguracionCamposComplejos] = None,
) -> str:
    """
    Genera HTML de fichas para registros complejos (objetos o simples).
    
    Argumentos:
        nombre_campo: Nombre del campo complejo a generar
        valor_anterior: Valor del campo antes de la corrección
        valor_corregido: Valor del campo después de la corrección
        config: ConfiguracionCamposComplejos (usa global si no se proporciona)
    
    Retorna:
        HTML con fichas comparadas
    """
    if config is None:
        config = _CONFIGURACION_GLOBAL
    configuracion = config.obtener(nombre_campo)
    registrosAntes = parsear_arreglo_valores(valor_anterior)
    registrosDespues = parsear_arreglo_valores(valor_corregido)

    if not registrosAntes and not registrosDespues:
        return '<div style="padding: 8px; color: #64748b;">Sin datos para mostrar.</div>'

    # Manejar arreglos simples (lista de strings)
    if configuracion.get('tipo') == 'arregloSimple':
        valoresAntes = [v for v in registrosAntes if isinstance(v, str)]
        valoresDespues = [v for v in registrosDespues if isinstance(v, str)]
        return generar_html_arreglo_simple(valoresAntes, valoresDespues, configuracion)

    # Manejar arreglos de objetos (fichas)
    pares = []
    for indice in range(max(len(registrosAntes), len(registrosDespues))):
        registroAntes = registrosAntes[indice] if indice < len(registrosAntes) else None
        registroDespues = registrosDespues[indice] if indice < len(registrosDespues) else None
        if registroAntes or registroDespues:
            pares.append({
                'antes': registroAntes,
                'despues': registroDespues,
                'esNuevo': not registroAntes,
                'esEliminado': not registroDespues,
            })

    htmlFichas = []
    for indice, parRegistro in enumerate(pares):
        etiqueta = 'Nuevo' if parRegistro['esNuevo'] else 'Eliminado' if parRegistro['esEliminado'] else f'Registro {indice + 1}'
        numeroId = (parRegistro['antes'] or {}).get('numero_id') or (parRegistro['despues'] or {}).get('numero_id') or ''

        filasTabla = []
        for campoDef in configuracion.get('campos', []):
            clave = campoDef['clave']
            etiquetaCampo = campoDef['etiqueta']
            valorAntes = (parRegistro['antes'] or {}).get(clave, '') if parRegistro['antes'] else ''
            valorDespues = (parRegistro['despues'] or {}).get(clave, '') if parRegistro['despues'] else ''
            seModifico = not son_valores_iguales(valorAntes, valorDespues)

            bgAntes = '#fff7ed' if (seModifico and parRegistro['antes']) else '#fff'
            bgDespues = '#f0fdf4' if (seModifico and parRegistro['despues']) else '#fff'

            filasTabla.append(f'''
                <tr>
                  <td style="padding: 6px 8px; color: #64748b; font-size: 11px; width: 30%;">{escape(etiquetaCampo)}</td>
                  <td style="padding: 6px 8px; background: {bgAntes}; width: 35%;">{escape(formatear_valor_campo(valorAntes, clave))}</td>
                  <td style="padding: 6px 8px; background: {bgDespues}; width: 35%;">{escape(formatear_valor_campo(valorDespues, clave))}</td>
                </tr>
            ''')

        htmlFicha = f'''
        <div style="border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px; margin-bottom: 10px; background: #fff;">
          <div style="font-weight: bold; color: #1e293b; margin-bottom: 8px; display: flex; justify-content: space-between;">
            <span>{escape(etiqueta)}</span>
            <span style="font-size: 11px; color: #64748b;">{escape(numeroId)}</span>
          </div>
          <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
            {''.join(filasTabla)}
          </table>
        </div>
        '''
        htmlFichas.append(htmlFicha)

    return ''.join(htmlFichas)
