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
