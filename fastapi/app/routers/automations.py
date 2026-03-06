from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.services import processor

router = APIRouter()


class ProcessRequest(BaseModel):
    action: str
    payload: dict = {}


class ProcessResponse(BaseModel):
    success: bool
    result: dict = {}
    message: str = ""


@router.post("/process", response_model=ProcessResponse)
async def process(request: ProcessRequest):
    """
    Endpoint genérico que n8n llama via HTTP Request node.
    El campo `action` determina qué lógica ejecutar.
    """
    logger.info(f"Procesando acción: {request.action} | payload: {request.payload}")
    try:
        result = await processor.handle(request.action, request.payload)
        return ProcessResponse(success=True, result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error procesando acción {request.action}: {e}")
        raise HTTPException(status_code=500, detail="Error interno procesando la acción") from e
