# ADR 001: n8n como orquestador de workflows

## Estado

Aceptada

## Contexto

Se necesita una plataforma para orquestar automaciones que incluya scheduling, webhooks, integraciones con servicios externos y una interfaz visual para disenar flujos. Las alternativas evaluadas fueron: n8n (self-hosted), Zapier (SaaS), Temporal (code-first) y scripts cron puros.

## Decision

Usar n8n self-hosted como orquestador de workflows.

## Consecuencias

**Positivas:**
- Interfaz visual para disenar y depurar flujos
- Self-hosted: control total sobre datos y costos predecibles
- Amplio ecosistema de nodos (400+) para integraciones
- Webhooks nativos para triggers externos
- Puede llamar a FastAPI via HTTP Request node

**Negativas:**
- Requiere mantener infraestructura (Docker)
- La logica compleja es mejor en Python que en nodos visuales (por eso existe FastAPI como complemento)
- Actualizaciones del contenedor requieren atencion manual
