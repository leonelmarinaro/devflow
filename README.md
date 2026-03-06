# devflow

![CI](https://github.com/leonelmarinaro/devflow/actions/workflows/ci.yml/badge.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)

Developer productivity toolkit: automatizaciones y workflows con FastAPI, n8n y PostgreSQL.

## Arquitectura

Ver [docs/architecture.md](docs/architecture.md) para el diagrama completo.

| Servicio | Rol | Puerto |
|----------|-----|--------|
| **FastAPI** | Action Dispatcher — lógica de automations | 8000 |
| **n8n** | Orquestador visual — scheduling, webhooks, integraciones | 5678 |
| **PostgreSQL** | Persistencia de n8n | interno |

El flujo estándar: **n8n** dispara un trigger (cron, webhook) → llama a **FastAPI** → FastAPI ejecuta la lógica y llama APIs externas.

## Requisitos

- Docker y Docker Compose
- Python 3.12+ (solo para desarrollo local)

## Instalacion rapida

```bash
git clone https://github.com/leonelmarinaro/devflow.git
cd devflow

cp .env.example .env
# Completar .env con valores reales

docker compose up -d
curl http://localhost:8000/health
```

## Desarrollo

```bash
make install       # Instalar dependencias de desarrollo
make check         # lint + format-check + typecheck + test
make lint          # Ruff check
make format        # Ruff format
make typecheck     # mypy
make test          # pytest
make test-cov      # pytest con cobertura
```

## Estructura

```
devflow/
├── fastapi/                       # Backend API
│   ├── app/
│   │   ├── main.py                # App FastAPI + health endpoint
│   │   ├── routers/
│   │   │   └── automations.py     # POST /api/automations/process
│   │   └── services/
│   │       ├── processor.py       # Action Dispatcher (registro de acciones)
│   │       └── github_standup.py  # Daily Standup: GitHub API → Slack + Obsidian
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── n8n/
│   └── backup/
│       └── daily_standup_workflow.json  # Workflow importable en n8n
├── postgres/
│   └── init/                      # Scripts de inicializacion de DB
├── docs/
│   ├── architecture.md            # Diagrama de arquitectura
│   └── adr/                       # Architecture Decision Records
├── docker-compose.yml
├── pyproject.toml                 # Configuracion ruff, mypy, pytest
└── Makefile
```

## Uso

### Action Dispatcher

El endpoint `POST /api/automations/process` es el punto de entrada único para todas las automatizaciones:

```bash
# Accion de prueba
curl -X POST http://localhost:8000/api/automations/process \
  -H "Content-Type: application/json" \
  -d '{"action": "echo", "payload": {"message": "hello"}}'

# Daily Standup manual
curl -X POST http://localhost:8000/api/automations/process \
  -H "Content-Type: application/json" \
  -d '{"action": "daily_standup", "payload": {}}'
```

Para agregar una nueva acción, ver `fastapi/app/services/processor.py`.

### Daily Standup

Recolecta actividad de GitHub (commits, PRs, issues) de la org configurada y envía el reporte a Slack + Obsidian. Se ejecuta automáticamente a las 8:45 AM de lunes a viernes desde n8n. Los lunes incluye datos del viernes al lunes.

El workflow de n8n está en `n8n/backup/daily_standup_workflow.json`.
Para importarlo: n8n → Workflows → Add workflow → Import from file.

Variables de entorno necesarias (ver `.env.example`):
- `GITHUB_TOKEN` — token OAuth con scopes `repo`, `read:org`
- `GITHUB_ORG`, `GITHUB_USERNAME` — organización y usuario a monitorear
- `SLACK_WEBHOOK_URL` — Incoming Webhook de Slack
- `OBSIDIAN_VAULT_PATH` — ruta absoluta a la vault (solo entorno local)

### n8n

Acceder a `http://localhost:5678`. Credenciales: `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD` del `.env`.

## Testing

```bash
make test                # Todos los tests
make test-cov            # Con reporte de cobertura
pytest fastapi/tests/ -v # Solo tests de FastAPI
```

## ADRs

- [001 - n8n como orquestador de workflows](docs/adr/001-n8n-como-orquestador.md)
- [002 - Patron Action Dispatcher para FastAPI](docs/adr/002-action-dispatcher-pattern.md)
- [003 - Ruff como linter y formatter unificado](docs/adr/003-ruff-como-linter-formatter.md)
- [004 - gh CLI sobre API REST](docs/adr/004-gh-cli-sobre-api-rest.md) *(supersedida)*
- [005 - GitHub REST API en Docker](docs/adr/005-github-rest-api-en-docker.md)

## Licencia

[MIT](LICENSE)
