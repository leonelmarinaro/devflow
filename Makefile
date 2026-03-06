.DEFAULT_GOAL := help

.PHONY: help install lint format format-check typecheck test test-cov check \
        docker-up docker-down docker-logs docker-build clean

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Instalar dependencias de desarrollo y proyecto
	pip install -r requirements-dev.txt -r fastapi/requirements.txt -r standup/requirements.txt

lint: ## Ejecutar ruff check
	ruff check .

format: ## Formatear codigo con ruff
	ruff format .

format-check: ## Verificar formato sin modificar
	ruff format --check .

typecheck: ## Ejecutar mypy
	mypy fastapi/app standup/

test: ## Ejecutar tests
	pytest

test-cov: ## Ejecutar tests con cobertura
	pytest --cov

check: lint format-check typecheck test ## Ejecutar todas las verificaciones

docker-up: ## Levantar servicios con Docker Compose
	docker compose up -d

docker-down: ## Detener servicios
	docker compose down

docker-logs: ## Ver logs de servicios
	docker compose logs -f

docker-build: ## Reconstruir imagenes
	docker compose build

clean: ## Limpiar caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage coverage.xml
