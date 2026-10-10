---
name: cost-aware-llm-pipeline
description: Cost optimization patterns for OpenRouter — model routing from .env, budget tracking, retry logic, and prompt caching. Cost read from usage.cost in the response, never hardcoded. Use when building features that call LLM APIs and need to track spend against the hackathon budget.
metadata:
  origin: ECC (adapted for OpenRouter; model names and prices come from .env and API response, not hardcoded)
---

# Cost-Aware LLM Pipeline — OpenRouter

Patrones para controlar el gasto en LLM. El modelo lo eliges tú en `.env`; el costo real lo devuelve OpenRouter en cada llamada.

## Variables de entorno requeridas

```bash
# .env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=<modelo para tareas complejas>        # lo eliges tú con el brief
OPENROUTER_MODEL_CHEAP=<modelo para tareas simples>    # opcional; si no se define, usa OPENROUTER_MODEL para todo
OPENROUTER_BUDGET_USD=<tope en USD>                    # OBLIGATORIA, sin valor por defecto; si falta, la API no arranca
# Ejemplo (no es un valor por defecto):  OPENROUTER_BUDGET_USD=35.00
```

> **Cómo fijar el tope:** sale de las reglas del evento (saldo de la llave y reservas, ver `RUBRICA.md` / `BRIEF.md`). Pon un número menor al saldo usable para dejar margen.

> **Cómo elegir el modelo:** cuando tengas el brief, busca en openrouter.ai/models los precios del día, compara calidad/costo, y escribe el nombre exacto en `.env`. No hay precios hardcodeados aquí porque cambian.

---

## 1. Cliente OpenRouter

OpenRouter usa la misma interfaz que OpenAI. La diferencia es la URL base y el campo `cost` en la respuesta.

```python
import os
from openai import OpenAI

def get_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
```

---

## 2. Routing de modelo por complejidad

Usa el modelo barato para tareas simples y el caro para las complejas. Si no hay modelo barato definido en `.env`, usa siempre el principal.

```python
def select_model(text_length: int, item_count: int) -> str:
    """Elige el modelo según complejidad de la tarea."""
    model_main  = os.environ["OPENROUTER_MODEL"]
    model_cheap = os.environ.get("OPENROUTER_MODEL_CHEAP", model_main)

    # Umbrales orientativos; ajustar según observación real
    THRESHOLD_CHARS = 10_000
    THRESHOLD_ITEMS = 30

    if text_length >= THRESHOLD_CHARS or item_count >= THRESHOLD_ITEMS:
        return model_main   # tarea compleja
    return model_cheap      # tarea simple
```

---

## 3. Leer el costo real de la respuesta

OpenRouter incluye `cost` dentro del objeto `usage` de cada respuesta. Es el costo real en USD de esa llamada.

```python
def extract_cost(response) -> float:
    """Lee el costo real devuelto por OpenRouter en usage.cost."""
    usage = response.usage
    if usage is None:
        return 0.0
    # El SDK de OpenAI mapea campos extra en model_extra
    extra = getattr(usage, "model_extra", None) or {}
    return float(extra.get("cost", 0.0))
```

---

## 4. Registro de costos inmutable

Cada llamada devuelve un registro nuevo; nunca se modifica el estado anterior. Hace que el historial de gasto sea fácil de auditar.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CostRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float          # leído de usage.cost, nunca calculado a mano

@dataclass(frozen=True, slots=True)
class CostTracker:
    budget_usd: float
    records: tuple[CostRecord, ...] = ()

    @classmethod
    def from_env(cls) -> "CostTracker":
        """Lee el tope de .env. No hay valor por defecto: si falta o es inválido, falla."""
        raw = os.environ.get("OPENROUTER_BUDGET_USD", "").strip()
        if not raw:
            raise RuntimeError(
                "Falta OPENROUTER_BUDGET_USD en .env: define el tope de gasto en USD "
                "(por ejemplo OPENROUTER_BUDGET_USD=35.00). No hay valor por defecto."
            )
        try:
            budget = float(raw)
        except ValueError:
            raise RuntimeError(
                f"OPENROUTER_BUDGET_USD debe ser un número en USD, pero vale {raw!r}."
            ) from None
        if not 0 < budget < float("inf"):
            raise RuntimeError(
                f"OPENROUTER_BUDGET_USD debe ser mayor que 0 y finito, pero vale {raw!r}."
            )
        return cls(budget_usd=budget)

    def add(self, record: CostRecord) -> "CostTracker":
        return CostTracker(budget_usd=self.budget_usd, records=(*self.records, record))

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def over_budget(self) -> bool:
        return self.total_cost > self.budget_usd

    @property
    def remaining(self) -> float:
        return self.budget_usd - self.total_cost
```

---

## 5. Reintentos solo en errores transitorios

Solo se reintenta cuando el error es temporal (red, rate limit, servidor). Errores permanentes (autenticación, request mal formado) fallan de inmediato para no gastar más presupuesto.

```python
import time
from openai import APIConnectionError, RateLimitError, InternalServerError

_RETRYABLE = (APIConnectionError, RateLimitError, InternalServerError)
_MAX_RETRIES = 3

def call_with_retry(func, *, max_retries: int = _MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            return func()
        except _RETRYABLE:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)   # espera 1 s, 2 s, 4 s
        # AuthenticationError, BadRequestError, etc. → se propagan sin reintentar
```

---

## 6. Caché de prompts largos

Si el system prompt tiene más de ~1000 tokens (palabras), marcarlo como cacheable evita pagarlo en cada llamada.

```python
def build_messages(system_prompt: str, user_input: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # OpenRouter lo pasa al proveedor
                },
                {
                    "type": "text",
                    "text": user_input,
                },
            ],
        }
    ]
```

---

## 7. Pipeline completo

```python
class BudgetExceededError(Exception):
    pass

def process(
    text: str,
    tracker: CostTracker,
    *,
    client: OpenAI | None = None,
    system_prompt: str = "",
) -> tuple[str, CostTracker]:
    if tracker.over_budget:
        raise BudgetExceededError(
            f"Presupuesto agotado: ${tracker.total_cost:.4f} / ${tracker.budget_usd:.2f}"
        )

    model = select_model(len(text), item_count=0)
    _client = client or get_client()

    response = call_with_retry(lambda: _client.chat.completions.create(
        model=model,
        messages=build_messages(system_prompt, text),
    ))

    record = CostRecord(
        model=model,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        cost_usd=extract_cost(response),   # costo real de OpenRouter
    )

    return response.choices[0].message.content, tracker.add(record)
```

---

## 8. Saldo real: consultarlo a OpenRouter

El `CostTracker` vive en memoria: si la API se reinicia (deploy, caída, `docker restart`), el contador vuelve a cero y "olvida" lo que ya se gastó. La fuente de verdad del saldo es OpenRouter:

```
GET https://openrouter.ai/api/v1/key
Authorization: Bearer <OPENROUTER_API_KEY>
```

Es una consulta de información de la llave, no una llamada a un modelo. Es gratis (lo indica el dueño del proyecto; la documentación de OpenRouter no lo afirma de forma explícita).

Campos útiles dentro de `data` (documentación oficial de OpenRouter):

| Campo | Significado |
|---|---|
| `usage` | Créditos gastados con esa llave, desde siempre |
| `usage_daily` | Gastado en el día UTC actual |
| `limit` | Tope de la llave; `null` = sin tope |
| `limit_remaining` | Lo que queda bajo ese tope; `null` = sin tope |

```python
import requests

def fetch_key_info() -> dict:
    """Consulta a OpenRouter el estado real de la llave. Lanza excepción si falla."""
    r = requests.get(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["data"]


def real_remaining_usd(tracker: CostTracker) -> float:
    """Lo que de verdad queda: el menor entre el presupuesto propio y el tope de la llave."""
    try:
        info = fetch_key_info()
    except requests.RequestException:
        return tracker.remaining   # sin red: usa el contador local y deja aviso en el log
    candidates = [tracker.budget_usd - float(info["usage"])]
    if info.get("limit_remaining") is not None:
        candidates.append(float(info["limit_remaining"]))
    return min(candidates)
```

Cuándo consultar:
- **Al arrancar la API**: así conoces el gasto previo aunque el contador esté en cero.
- **Antes de una tanda grande de llamadas**, o cada cierto número de casos.
- **No en cada request**: suma latencia y compite con el límite de tiempo por caso.

Si el resultado es ≤ 0, no llames más a modelos. Si la consulta falla, no bloquees el servicio: usa el contador local y registra el aviso.

---

## Buenas prácticas

- **Elige el modelo con el brief en mano**: compara calidad necesaria vs precio del día en openrouter.ai/models.
- **Establece el tope antes de procesar**: `CostTracker.from_env()` lo lee de `.env` y falla con un mensaje claro si falta; nunca asumas un valor.
- **Consulta el saldo real a OpenRouter** (`GET /api/v1/key`) al arrancar y antes de tandas grandes; el contador en memoria se pierde al reiniciar.
- **Loguea cada selección de modelo**: ayuda a ajustar umbrales con datos reales.
- **Usa caché** para system prompts que se repiten en muchas llamadas.
- **Nunca reintentar errores de autenticación**: solo gastarías más presupuesto.

## Anti-patrones

- Hardcodear nombres de modelo en el código — van en `.env`.
- Poner un valor por defecto al tope de gasto: un número olvidado en el código se vuelve el límite real sin que nadie lo decida.
- Calcular el costo a mano con precios fijos — usar `usage.cost` de la respuesta.
- Reintentar todos los errores — solo los transitorios.
- Ignorar `over_budget` antes de cada llamada.
- Confiar solo en el contador en memoria: se borra al reiniciar la API; el saldo real se consulta a OpenRouter.
- Mutar el CostTracker en vez de crear uno nuevo — dificulta auditar el gasto.
