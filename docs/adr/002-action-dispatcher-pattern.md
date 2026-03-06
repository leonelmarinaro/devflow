# ADR 002: Patron Action Dispatcher para FastAPI

## Estado

Aceptada

## Contexto

n8n necesita ejecutar logica Python compleja. Se evaluo: un endpoint por accion vs un endpoint unico con despacho por campo `action`. Con multiples endpoints, cada nueva accion requiere agregar ruta, schema y wiring. Con el dispatcher, solo se necesita una funcion y una entrada en el dict.

## Decision

Usar un unico endpoint `POST /api/automations/process` que recibe `{action: str, payload: dict}` y despacha a funciones registradas en `ACTION_HANDLERS`.

## Consecuencias

**Positivas:**
- Agregar acciones es trivial (funcion + entrada en dict)
- n8n solo necesita configurar un HTTP Request node
- Facil de testear: cada handler es una funcion async independiente

**Negativas:**
- Menor descubribilidad via OpenAPI (un solo endpoint generico)
- Validacion del payload es generica (dict), no tipada por accion
- Si el numero de acciones crece mucho, considerar migrar a endpoints dedicados
