"""
Despachador de acciones: n8n llama a /api/automations/process con una `action`,
este módulo la mapea a la función Python correspondiente.

Para agregar una nueva acción:
1. Definir la función async en este módulo (o importarla de otro módulo)
2. Registrarla en el dict ACTION_HANDLERS
"""
from loguru import logger


async def echo(payload: dict) -> dict:
    """Acción de prueba: devuelve el payload recibido."""
    return {"echo": payload}


# Registrar acciones aquí
ACTION_HANDLERS = {
    "echo": echo,
    # "scrape_url": scraper.scrape,
    # "process_document": documents.process,
}


async def handle(action: str, payload: dict) -> dict:
    handler = ACTION_HANDLERS.get(action)
    if not handler:
        raise ValueError(f"Acción desconocida: '{action}'. Disponibles: {list(ACTION_HANDLERS.keys())}")
    return await handler(payload)
