# FastAPI Backend

## Stack

- FastAPI 0.115.6 + Pydantic v2 + loguru
- Python 3.12, uvicorn con hot-reload en dev

## Patron

Action Dispatcher: el endpoint `/api/automations/process` recibe `{action, payload}` y despacha a la funcion registrada en `ACTION_HANDLERS` (`services/processor.py`).

## Agregar una accion nueva

1. Crear funcion `async def mi_accion(payload: dict) -> dict` en `processor.py` o en un modulo nuevo bajo `services/`
2. Registrar en `ACTION_HANDLERS["mi_accion"] = mi_accion`
3. Agregar test en `tests/`

## Tests

- Framework: pytest + httpx TestClient
- `conftest.py` provee fixture `client`
- Ejecutar: `pytest fastapi/tests/ -v`
