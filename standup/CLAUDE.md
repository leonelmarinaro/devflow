# Daily Standup Script

## Descripcion

Script standalone que genera reportes diarios de actividad GitHub y los envia a Telegram + Obsidian.

## Dependencias

- `gh` CLI para datos de GitHub (no usa API REST directamente)
- `requests` para Telegram API
- `python-dotenv` para variables de entorno

## Variables de entorno

Ver `standup/.env.example`. Principales: `GITHUB_ORG`, `GITHUB_USERNAME`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OBSIDIAN_VAULT_PATH`.

## Modo dry-run

`python3 daily_standup.py --dry-run` imprime el reporte sin enviar. La variable `DRY_RUN` se evalua a nivel modulo.

## Formatos de salida

- **Markdown**: para Obsidian, con frontmatter YAML
- **Telegram MarkdownV2**: con caracteres escapados via `esc()`

## Tests

- Los tests deben mockear `sys.argv` antes de importar el modulo (ver `conftest.py`)
- Ejecutar: `pytest standup/tests/ -v`
