"""
Constantes de dominio compartidas entre servicios.

Centraliza valores que deben permanecer sincronizados entre múltiples capas
(servicios, migraciones, frontend) para evitar magic strings duplicados.
"""

# Sincronizar con: frontend/src/components/portal-interno/constantes.js

# PDF oficial del formulario SAGRILAFT generado al enviarlo a firma.
TIPO_DOCUMENTO_FORMULARIO_PDF = "FORMULARIO_PDF"

# Certificado de Terceros SAGRILAFT generado automáticamente al iniciar la firma.
# Se persiste en documentos_adjuntos para trazabilidad de auditoría, pero no se
# expone como adjunto del diligenciamiento en la UI (es un artefacto de firma).
TIPO_DOCUMENTO_CERTIFICADO_SAGRILAFT = "CERTIFICADO_SAGRILAFT"
