# Coding Standards — devflow

## Python

- Line length: 100
- Linter/Formatter: ruff
- Type checker: mypy (modo gradual, ignore_missing_imports)
- Tests: pytest + pytest-asyncio
- Imports ordenados (isort via ruff)
- No dejar imports sin usar
- No usar `print()` para logging — usar `logging` o `loguru`
- Funciones async cuando el framework lo requiera (FastAPI)
- Type hints en firmas de funciones publicas

## Estilo

- Nombres de variables y funciones en snake_case
- Constantes en UPPER_SNAKE_CASE
- Funciones privadas con prefijo `_`
- Docstrings solo donde la logica no sea obvia
- No agregar comentarios redundantes que repitan lo que el codigo dice
- No sobre-documentar ni agregar type annotations a codigo no modificado
- En archivos de test (`test_*.py`): no se requieren type hints, docstrings ni logging — los tests priorizan claridad y brevedad

## Seguridad

- No commitear secretos (.env, tokens, API keys, passwords)
- No usar `eval()`, `exec()`, o `subprocess.run(shell=True)`
- Validar input externo (user input, APIs) — no confiar en datos internos
- No introducir SQL injection, XSS, command injection

## Simplicidad

- No agregar abstracciones prematuras ni helpers para operaciones unicas
- No agregar error handling para escenarios imposibles
- No agregar features no solicitadas
- Tres lineas similares son mejores que una abstraccion prematura
- Preferir claridad sobre cleverness
