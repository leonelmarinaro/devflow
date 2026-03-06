# devflow - Guia para Claude

## Descripcion

Developer productivity toolkit. FastAPI como backend de automations con n8n como orquestador y PostgreSQL como persistencia. Todo corre en Docker Compose.

## Estructura

- `fastapi/app/services/processor.py` - Action Dispatcher (registro central de acciones)
- `fastapi/app/services/github_standup.py` - Daily Standup: GitHub REST API → Slack + Obsidian
- `n8n/backup/` - Workflows exportados de n8n (versionados, importables via UI)
- `docker-compose.yml` - PostgreSQL + n8n + FastAPI
- `docs/` - Arquitectura y ADRs

## Convenciones

- **Linter/Formatter**: ruff (configurado en pyproject.toml)
- **Type checker**: mypy (modo gradual, ignore_missing_imports)
- **Tests**: pytest + pytest-asyncio. Path: `fastapi/tests/`
- **Commits**: en espanol, imperativo, sin punto final
- **Line length**: 100

## Comandos utiles

```bash
make check                  # lint + format-check + typecheck + test
make test                   # solo tests
make lint                   # solo ruff check
make typecheck              # solo mypy
docker compose up -d        # levantar stack completo
docker compose logs fastapi # ver logs de FastAPI
```

## Patron Action Dispatcher (FastAPI)

Las acciones se registran en `fastapi/app/services/processor.py` en el dict `ACTION_HANDLERS`.
Para agregar una accion nueva:
1. Crear modulo en `fastapi/app/services/mi_accion.py` con funcion `async def mi_accion(payload: dict) -> dict`
2. Importar y registrar en `processor.py`: `ACTION_HANDLERS["mi_accion"] = mi_accion`
3. Agregar tests en `fastapi/tests/`
4. Si tiene trigger programado, crear workflow en n8n y exportarlo a `n8n/backup/`

### Acciones registradas

| Accion | Modulo | Descripcion |
|---|---|---|
| `echo` | `processor.py` | Test: devuelve el payload recibido |
| `github_standup` | `services/github_standup.py` | Daily Standup: GitHub REST API → Slack + Obsidian |
| `generate_invoice` | `services/invoices.py` | Genera factura PDF mensual desde plantilla .docx |

## Daily Standup (`github_standup.py`)

- Usa GitHub REST API con `httpx.AsyncClient` (token via `GITHUB_TOKEN`)
- Filtra merge commits automaticamente (prefijos: "Merge pull request", "Merge branch", "Merge remote-tracking")
- Agrupa actividad por repositorio en ambos formatos de salida
- Salida dual: Slack Block Kit (Incoming Webhook) + Markdown para Obsidian
- El path de Obsidian se monta como bind volume: `$OBSIDIAN_VAULT_PATH/00-Inbox:/obsidian-inbox`
- Programado en n8n: cron `45 8 * * 1-5` (lun-vie 8:45 AM, timezone ART)
- Los lunes extiende el rango al viernes anterior (3 dias atras)

## Facturacion mensual (generate_invoice)

- Plantilla: `/Users/lmarinaro/Documents/Leo/Facturas/EXT - MAKE A COPY - Modelo Factura Contractor GKT.docx`
- Output: `/Users/lmarinaro/Documents/Leo/Facturas/leonel-marinaro_YYYY-MM.pdf`
- Edita campos `Date:`, `Due Date:` e `Invoice No:` en el .docx usando `python-docx` (preserva formato de runs)
- Invoice No se auto-incrementa contando PDFs existentes en output dir (INV000001, INV000002, ...)
- Convierte a PDF con LibreOffice headless (`soffice --headless --convert-to pdf`)
- Notifica por Slack via `SLACK_WEBHOOK_URL` (env var, mismo webhook que standup)
- Dependencia externa: `brew install --cask libreoffice`
- Payload opcional: `date` (YYYY-MM-DD), `template_path`, `output_dir`
- Sin payload, usa fecha = 1ro del mes actual

## Variables de entorno clave (root .env)

Ver `.env.example`. Esenciales para las automations:
- `GITHUB_TOKEN` - Token OAuth de GitHub (obtener con `gh auth token`)
- `GITHUB_ORG`, `GITHUB_USERNAME` - Org y usuario a monitorear
- `SLACK_WEBHOOK_URL` - Incoming Webhook URL de Slack
- `OBSIDIAN_VAULT_PATH` - Ruta absoluta a vault Obsidian (solo entorno local; vaciar en VPS)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Disponibles para futuros triggers
