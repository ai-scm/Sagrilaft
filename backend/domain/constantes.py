"""
Constantes de dominio compartidas entre servicios.

Centraliza valores que deben permanecer sincronizados entre múltiples capas
(servicios, migraciones, frontend) para evitar magic strings duplicados.
"""

# Sincronizar con: frontend/apps/portal-interno/src/config/constantes.js

# PDF oficial del formulario SAGRILAFT generado al enviarlo a firma.
TIPO_DOCUMENTO_FORMULARIO_PDF = "FORMULARIO_PDF"

# Certificado de Terceros SAGRILAFT generado automáticamente al iniciar la firma.
# Se persiste en documentos_adjuntos para trazabilidad de auditoría, pero no se
# expone como adjunto del diligenciamiento en la UI (es un artefacto de firma).
TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT = "CERTIFICADO_SAGRILAFT"

# Límite de porcentaje para participación accionaria y coerciones de porcentaje.
PORCENTAJE_MAXIMO_PERMITIDO = 100

# Reporte final cargado manualmente para marcar el cierre de la carpeta del proceso.
TIPO_DOCUMENTO_REPORTE_FINAL = "REPORTE_FINAL"

# Causales de cierre de expediente.
CAUSAL_CIERRE_INFORME_FINAL = "informe_final"
CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS = "no_continuacion_dialogos"
CAUSAL_CIERRE_RECHAZADO_CON_INFORME_FINAL = "rechazado_con_informe_final"

CAUSALES_CIERRE_EXPEDIENTE = {
    CAUSAL_CIERRE_INFORME_FINAL,
    CAUSAL_CIERRE_NO_CONTINUACION_DIALOGOS,
    CAUSAL_CIERRE_RECHAZADO_CON_INFORME_FINAL,
}

# Modos de trabajo cuando un expediente vuelve a estar editable.
MODO_TRABAJO_CORRECCION = "correccion"
MODO_TRABAJO_ACTUALIZACION_REABIERTA = "actualizacion_reabierta"
