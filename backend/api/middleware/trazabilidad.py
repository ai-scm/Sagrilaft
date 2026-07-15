import uuid
import contextvars
import logging
from fastapi import Request

# ContextVar para almacenar el request_id por cada request concurrente
request_id_context = contextvars.ContextVar("request_id", default="-")

class RequestIdFilter(logging.Filter):
    """Filtro de logging para inyectar el request_id en cada registro de log."""
    def filter(self, record):
        record.request_id = request_id_context.get()
        return True

async def trazabilidad_middleware(request: Request, call_next):
    """
    Middleware que genera un ID único por petición,
    lo guarda en el contexto para logs y lo devuelve en los headers.
    """
    req_id = str(uuid.uuid4())
    token = request_id_context.set(req_id)
    
    # También lo inyectamos en el state de FastAPI por conveniencia
    request.state.request_id = req_id
    
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_context.reset(token)
