# devflow

![CI](https://github.com/leonelmarinaro/devflow/actions/workflows/ci.yml/badge.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)
![mypy](https://img.shields.io/badge/mypy-checked-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg)

Developer productivity toolkit: automaciones, workflows y herramientas de desarrollo con FastAPI, n8n y scripts de productividad.

## Arquitectura

Ver [docs/architecture.md](docs/architecture.md) para el diagrama completo.

**Componentes principales:**

- **FastAPI** - Backend Python con patrón Action Dispatcher para procesar solicitudes de n8n
- **n8n** - Orquestador visual de workflows (webhooks, scheduling, integraciones)
- **PostgreSQL** - Base de datos compartida por n8n
- **Daily Standup** - Script standalone que recolecta actividad de GitHub y la envía a Telegram + Obsidian

## Requisitos

- Python 3.12+
- Docker y Docker Compose
- `gh` CLI (para el script de standup)

## Instalacion rapida

```bash
# Clonar el repositorio
git clone https://github.com/leonelmarinaro/devflow.git
cd devflow

# Copiar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Levantar servicios
docker compose up -d

# Verificar
curl http://localhost:8000/health
```

## Desarrollo

```bash
# Instalar dependencias de desarrollo
make install

# Ejecutar todas las verificaciones
make check

# Comandos individuales
make lint          # Ruff check
make format        # Ruff format
make typecheck     # mypy
make test          # pytest
make test-cov      # pytest con cobertura
```

## Estructura del proyecto

```
devflow/
├── fastapi/               # Backend API
│   ├── app/
│   │   ├── main.py        # App FastAPI + health endpoint
│   │   ├── routers/       # Endpoints (automations/process)
│   │   └── services/      # Logica de negocio (processor.py)
│   ├── tests/             # Tests del API
│   ├── Dockerfile
│   └── requirements.txt
├── standup/               # Script de Daily Standup
│   ├── daily_standup.py   # Script principal
│   ├── tests/             # Tests del standup
│   └── requirements.txt
├── n8n/                   # Configuracion n8n
│   └── backup/            # Backups de workflows
├── postgres/              # Configuracion PostgreSQL
│   └── init/              # Scripts de inicializacion
├── docs/                  # Documentacion
│   ├── architecture.md    # Diagrama de arquitectura
│   └── adr/               # Architecture Decision Records
├── docker-compose.yml
├── pyproject.toml         # Configuracion de herramientas (ruff, mypy, pytest)
├── Makefile               # Comandos de desarrollo
└── .pre-commit-config.yaml
```

## Uso

### FastAPI - Action Dispatcher

El endpoint `/api/automations/process` recibe un JSON con `action` y `payload`:

```bash
curl -X POST http://localhost:8000/api/automations/process \
  -H "Content-Type: application/json" \
  -d '{"action": "echo", "payload": {"message": "hello"}}'
```

Para agregar nuevas acciones, ver `fastapi/app/services/processor.py`.

### Daily Standup

```bash
cd standup
python3 daily_standup.py --dry-run   # Preview sin enviar
python3 daily_standup.py             # Enviar a Telegram + Obsidian
```

## Testing

```bash
make test                    # Todos los tests
make test-cov                # Con reporte de cobertura
pytest fastapi/tests/ -v     # Solo tests de FastAPI
pytest standup/tests/ -v     # Solo tests de standup
```

## ADRs

- [001 - n8n como orquestador de workflows](docs/adr/001-n8n-como-orquestador.md)
- [002 - Patron Action Dispatcher para FastAPI](docs/adr/002-action-dispatcher-pattern.md)
- [003 - Ruff como linter y formatter unificado](docs/adr/003-ruff-como-linter-formatter.md)
- [004 - gh CLI sobre API REST directa](docs/adr/004-gh-cli-sobre-api-rest.md)

## Licencia

[MIT](LICENSE)
