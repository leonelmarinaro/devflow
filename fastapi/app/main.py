from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.routers import automations

app = FastAPI(
    title="Automations API",
    description="Backend Python para flujos orquestados por n8n",
    version="0.1.0",
)

app.include_router(automations.router, prefix="/api/automations", tags=["automations"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado en {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
