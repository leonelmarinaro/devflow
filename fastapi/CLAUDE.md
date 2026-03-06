# FastAPI Backend

## Stack

- FastAPI 0.115.6 + Pydantic v2 + loguru
- Python 3.12, uvicorn con hot-reload en dev
- httpx para llamadas HTTP async (GitHub API, Slack)

## Patron

Action Dispatcher: el endpoint `/api/automations/process` recibe `{action, payload}` y despacha a la funcion registrada en `ACTION_HANDLERS` (`services/processor.py`).

## Servicios registrados

| Accion | Modulo | Descripcion |
|--------|--------|-------------|
| `echo` | `processor.py` | Eco del payload, para pruebas |
| `daily_standup` | `github_standup.py` | Actividad GitHub → Slack + Obsidian |

### github_standup.py

- Consulta GitHub REST API: `/search/commits` y `/search/issues` (cubre PRs e issues)
- Filtra merge commits automaticos (`_is_merge_commit`)
- Agrupa actividad por repositorio (`_group_by_repo`)
- Genera Slack Block Kit (`_format_slack`) y Markdown Obsidian (`_format_markdown`)
- Envia a Slack via Incoming Webhook (`_send_slack`)
- Escribe `/obsidian-inbox/daily_report_YYYY-MM-DD.md` (`_write_obsidian`)
- Variables de entorno requeridas: `GITHUB_TOKEN`, `GITHUB_ORG`, `GITHUB_USERNAME`, `SLACK_WEBHOOK_URL`
- Variable opcional: `OBSIDIAN_INBOX_PATH` (default `/obsidian-inbox`)
- Lunes: rango extendido a viernes anterior

## Agregar una accion nueva

1. Crear funcion `async def mi_accion(payload: dict) -> dict` en un modulo nuevo bajo `services/`
2. Importar y registrar en `ACTION_HANDLERS["mi_accion"] = mi_accion` en `processor.py`
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
