# ADR 005: GitHub REST API directa en contexto Docker

## Estado

Aceptada (supersede ADR-004)

## Contexto

El Daily Standup fue inicialmente implementado como un script standalone en `standup/` que usaba `gh` CLI via `subprocess` (ADR-004). Al migrar la lógica a FastAPI dentro de un contenedor Docker, el `gh` CLI no está disponible dentro del contenedor sin montajes adicionales del host, lo que complica el setup y rompe la portabilidad hacia VPS.

## Decision

Migrar a GitHub REST API directa usando `httpx.AsyncClient` (ya presente en las dependencias de FastAPI). Autenticación via `GITHUB_TOKEN` en variables de entorno.

## Consecuencias

**Positivas:**
- Sin dependencia del binario `gh` — el contenedor es autocontenido
- Deployable en VPS sin cambios
- API async nativa con `httpx.AsyncClient` — consistente con el stack FastAPI
- Control explícito sobre paginación y rate limiting
- Tests más simples: mockear `httpx` es más ergonómico que mockear `subprocess`

**Negativas:**
- Requiere gestionar el `GITHUB_TOKEN` manualmente (antes `gh auth` lo manejaba)
- El token debe renovarse cuando expire (los tokens OAuth de `gh` son de larga duración)
- Ligera pérdida de ergonomía en debugging (no se puede copiar el comando a la terminal)

## Implementacion

- Módulo: `fastapi/app/services/github_standup.py`
- Cliente: `httpx.AsyncClient` con header `Authorization: Bearer {GITHUB_TOKEN}`
- Endpoints usados: `GET /search/commits`, `GET /search/issues` (cubre PRs e issues)
- El token se obtiene inicialmente con `gh auth token` y se copia al `.env`
