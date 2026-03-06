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

## Accion: generate_invoice (`services/invoices.py`)

Genera factura PDF mensual. Flujo: plantilla .docx → editar fechas con python-docx → PDF con LibreOffice headless → notificar Slack.

- `_update_dates()`: reemplaza runs en parrafos `Date:` y `Due Date:` (cuidado: docx fragmenta texto en multiples runs)
- `_update_invoice_number()`: reemplaza `Invoice No:` con numero auto-incrementado
- `_next_invoice_number()`: cuenta `leonel-marinaro_*.pdf` en output dir + 1, formato `INV000XXX`
- `_convert_to_pdf()`: usa soffice headless, busca en `/Applications/LibreOffice.app/` o PATH
- `_notify_slack()`: POST async a webhook con httpx
- Env var requerida para Slack: `SLACK_WEBHOOK_URL`

## Tests

- Framework: pytest + httpx TestClient
- `conftest.py` provee fixture `client`
- Ejecutar: `pytest fastapi/tests/ -v`
- Tests de invoices mockean `subprocess.run` y `_find_soffice` para evitar dependencia de LibreOffice
