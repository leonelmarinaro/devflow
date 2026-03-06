# devflow - Guia para Claude

## Descripcion

Developer productivity toolkit. Monorepo con dos componentes Python independientes mas infraestructura Docker.

## Estructura

- `fastapi/` - API backend (FastAPI 0.115 + Pydantic v2 + loguru)
- `standup/` - Script standalone de Daily Standup (sin framework, usa gh CLI)
- `docker-compose.yml` - PostgreSQL + n8n + FastAPI
- `docs/` - Arquitectura y ADRs

## Convenciones

- **Linter/Formatter**: ruff (configurado en pyproject.toml)
- **Type checker**: mypy (modo gradual, ignore_missing_imports)
- **Tests**: pytest + pytest-asyncio. Paths: `fastapi/tests/`, `standup/tests/`
- **Commits**: en espanol, imperativo, sin punto final
- **Line length**: 100

## Comandos utiles

```bash
make check       # lint + format-check + typecheck + test
make test        # solo tests
make lint        # solo ruff check
make typecheck   # solo mypy
```

## Patron Action Dispatcher (FastAPI)

Las acciones se registran en `fastapi/app/services/processor.py` en el dict `ACTION_HANDLERS`.
Para agregar una accion: crear funcion async, registrarla en el dict.
El router en `automations.py` despacha via `processor.handle(action, payload)`.

## Daily Standup

- Script en `standup/daily_standup.py`
- Usa `gh` CLI para obtener datos de GitHub (commits, PRs, issues)
- Salida dual: Telegram (MarkdownV2) + Obsidian (Markdown)
- Variable `DRY_RUN` se evalua a nivel modulo desde `sys.argv`
- Tests deben mockear `sys.argv` antes de importar el modulo
