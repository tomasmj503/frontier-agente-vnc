---
name: search-first
description: Research-before-coding workflow — search PyPI, MCP servers, and GitHub for existing tools before writing custom code, then adopt, extend, or build. Use when starting a feature or about to write a utility that may already exist.
metadata:
  origin: ECC (adapted — removed references to ECC-specific agents)
---

# Search First — Investiga antes de codear

Antes de escribir código nuevo, busca si ya existe una solución.

## Flujo

```
┌─────────────────────────────────────────────┐
│  0. PREFLIGHT                               │
│     Verificar qué canales de búsqueda       │
│     están disponibles; reportar los         │
│     que se salten                           │
├─────────────────────────────────────────────┤
│  1. ANÁLISIS DE NECESIDAD                   │
│     ¿Qué funcionalidad se necesita?         │
│     ¿Qué lenguaje y restricciones hay?      │
├─────────────────────────────────────────────┤
│  2. BÚSQUEDA PARALELA                       │
│     ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│     │  PyPI /  │ │  MCP /   │ │  GitHub  │  │
│     │  npm     │ │  Skills  │ │  / Web   │  │
│     └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────┤
│  3. EVALUAR candidatos                      │
│     (funcionalidad, mantenimiento,          │
│      comunidad, docs, licencia, deps)       │
├─────────────────────────────────────────────┤
│  4. DECIDIR                                 │
│     ┌─────────┐  ┌──────────┐  ┌─────────┐  │
│     │ Adoptar │  │ Extender │  │Construir│  │
│     │ tal cual│  │ /Envolver│  │ custom  │  │
│     └─────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────┤
│  5. IMPLEMENTAR                             │
│     Instalar paquete / Configurar MCP /     │
│     Escribir el mínimo de código propio     │
└─────────────────────────────────────────────┘
```

## Tabla de decisión

| Señal | Acción |
|-------|--------|
| Coincidencia exacta, bien mantenida, MIT/Apache | **Adoptar** — instalar y usar directamente |
| Coincidencia parcial, buena base | **Extender** — instalar + escribir wrapper fino |
| Varios matches débiles | **Componer** — combinar 2-3 paquetes pequeños |
| Nada adecuado encontrado | **Construir** — código propio, pero informado por la búsqueda |

## Paso 0: Preflight

| Canal | Cómo verificar | Si no está disponible |
|-------|---------------|----------------------|
| Repo actual | `rg --files` y búsquedas con `rg` | Anotar que solo se revisaron archivos visibles |
| PyPI | `python -m pip --version` | Buscar en web/docs y no afirmar cobertura del registry |
| npm | `npm --version` | Ídem |
| GitHub CLI | `gh auth status` | Usar búsqueda web pública o historial git local |
| MCP/docs | Lista de herramientas disponibles | Recurrir a docs oficiales / búsqueda web |
| Skills locales | `ls .claude/skills/` | Indicar que no hay catálogo local de skills |

## Modo rápido (inline)

Antes de escribir una utilidad, pasar mentalmente por:

0. ¿Ya existe en el repo? → buscar con `rg` primero
1. ¿Es un problema común? → buscar en PyPI / npm
2. ¿Hay un MCP para esto? → revisar `~/.claude/settings.json`
3. ¿Hay una skill para esto? → revisar `.claude/skills/`
4. ¿Hay una implementación en GitHub? → buscar OSS mantenido antes de escribir desde cero

## Atajos por categoría

### Python / Backend
- HTTP client → `httpx` (async nativo, retries, timeouts)
- Scraping HTML → `beautifulsoup4` + `lxml`
- Validación de datos → `pydantic`
- API REST → `fastapi` + `uvicorn`
- Variables de entorno → `python-dotenv`
- Tests → `pytest`
- Lint → `ruff`

### AI / LLM
- OpenRouter → SDK de OpenAI apuntando a `https://openrouter.ai/api/v1`
- Anthropic SDK → ver `cost-aware-llm-pipeline` skill para patrones de costo

### CI / Calidad
- Pre-commit → `pre-commit`
- Formateo → `black` o `ruff format`

## Anti-patrones

- **Saltar al código** sin buscar si ya existe
- **Ignorar MCP** — puede que el servidor MCP ya tenga la capacidad
- **Silencio selectivo** — si un canal de búsqueda no estaba disponible, decirlo
- **Sobre-customizar** una librería hasta perder sus ventajas
- **Inflar dependencias** — instalar un paquete enorme por una función pequeña
