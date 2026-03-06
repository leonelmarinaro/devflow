# ADR 004: gh CLI sobre API REST directa para GitHub

## Estado

Supersedida por [ADR-005](005-github-rest-api-en-docker.md)

## Contexto

El script de Daily Standup necesita consultar datos de GitHub (commits, PRs, issues). Las opciones son: usar la API REST de GitHub directamente con `requests`/`httpx`, usar la libreria `PyGithub`, o usar el CLI oficial `gh`.

## Decision

Usar `gh` CLI via `subprocess.run` para todas las consultas a GitHub.

## Consecuencias

**Positivas:**
- Autenticacion manejada automaticamente por `gh auth` (no hay tokens en el codigo)
- Salida JSON nativa con `--json`
- Busqueda avanzada con `gh search` (commits, prs, issues)
- Sin dependencia adicional de Python (solo `subprocess`)
- Facil de depurar: los mismos comandos se pueden probar en terminal

**Negativas:**
- Requiere `gh` CLI instalado en el sistema
- Menor control sobre paginacion y rate limiting
- Parseo de JSON desde stdout (puede fallar si el formato cambia)
- Los tests requieren mockear `subprocess.run`
