# ADR 003: Ruff como linter y formatter unificado

## Estado

Aceptada

## Contexto

Se necesita un linter y formatter para mantener la calidad y consistencia del codigo Python. Las alternativas son: flake8 + black + isort (tres herramientas separadas) vs ruff (herramienta unificada).

## Decision

Usar ruff como linter y formatter unificado, reemplazando flake8, black e isort.

## Consecuencias

**Positivas:**
- Una sola herramienta en lugar de tres
- Ordenes de magnitud mas rapido que las alternativas
- Configuracion centralizada en `pyproject.toml`
- Compatible con las reglas de flake8, isort y mas
- Soporte nativo de pre-commit

**Negativas:**
- Proyecto relativamente nuevo (aunque con adopcion masiva)
- Algunas reglas pueden diferir sutilmente de las herramientas originales
