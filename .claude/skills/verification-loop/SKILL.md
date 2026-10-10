---
name: verification-loop
description: Seven-step verification for Python projects — tool check, lint, types, tests, security (secret scan over every repo file), diff review, and API contract tests read from the current DISENO.md, run against both the local and the public URL. Run after completing a feature, before creating a PR, and always before git push.
license: MIT
metadata:
  origin: ECC (adapted for Python + FastAPI + hackathon contract tests; cases come from DISENO.md, never hardcoded here)
---

# Verification Loop

Run all phases in order. Stop and fix before continuing if a phase fails.

## Phase 0: Herramientas

```bash
for t in ruff pyright pytest; do command -v "$t" >/dev/null && echo "✓ $t" || echo "✗ $t NO instalado"; done
```

Si falta alguna, instalarla antes de seguir (no saltarse la fase):

```bash
# Recomendado: dentro del entorno virtual del proyecto
python3 -m venv .venv && source .venv/bin/activate
pip install ruff pyright pytest

# Alternativa en macOS (instalación global)
brew install ruff pyright
```

- `ruff` revisa estilo y errores de lógica; `pyright` revisa tipos; `pytest` corre las pruebas.
- El paquete `pyright` de pip descarga Node.js la primera vez que se ejecuta: necesita internet y esa primera corrida es más lenta.
- Confirmar que `.venv/` está en `.gitignore` antes de hacer commit.

## Phase 1: Lint

```bash
ruff check . 2>&1 | head -30
```

Reports style and logic errors. Fix all errors; warnings are optional.

## Phase 2: Type check

```bash
pyright . 2>&1 | head -30
```

Reports type inconsistencies (variables usados con el tipo equivocado). Fix critical errors.

## Phase 3: Tests

```bash
pytest --tb=short -q 2>&1 | tail -40
```

Report:
- Total: X
- Passed: X
- Failed: X
- Coverage (if configured): X%

Target: 0 failures before push.

## Phase 4: Security — OBLIGATORIO antes de cada push

Busca secretos en **todos** los archivos del repo (código, `.md`, `.yml`, `.json`, `.txt`, Dockerfile…), tanto los rastreados por git como los nuevos sin rastrear. Los archivos ignorados por `.gitignore` (como `.env`) no se escanean, que es lo correcto.

```bash
# -l: muestra SOLO nombres de archivo, nunca el valor del secreto
FILES=$(git grep -lIiE --untracked \
  -e "sk-or-[A-Za-z0-9_-]{20,}" \
  -e "OPENROUTER_API_KEY[[:space:]]*[:=][[:space:]]*[\"']?[A-Za-z0-9_-]{20,}" \
  -e "(api[_-]?key|secret|passw(or)?d|token)[\"']?[[:space:]]*[:=][[:space:]]*[\"'][A-Za-z0-9_/+=.-]{20,}[\"']")
if [ -n "$FILES" ]; then echo "⚠ ALERTA: posible secreto en:"; echo "$FILES"; else echo "✓ sin secretos en ningún archivo del repo"; fi

# Verificar que .env NO está rastreado por git
git ls-files --error-unmatch .env 2>&1 | grep -q "did not match" && echo "✓ .env no está en git" || echo "⚠ ALERTA: .env está en git — quítalo antes de push"

# .env no debe aparecer en el diff del commit
git diff --cached --name-only | grep "^\.env$" && echo "⚠ ALERTA: .env está en el staging area" || echo "✓ .env no en staging"
```

Los patrones no incluyen nombres de cabeceras propias de un reto; el último patrón cubre cualquier `token`/`secret`/`api_key` asignado a un valor largo. Si el brief define una cabecera de autenticación con nombre propio y su valor aparece escrito en un archivo, añadir un `-e` con ese nombre (tomado de `BRIEF.md`).

Si aparece algún archivo: STOP. No hacer push. Abrir el archivo localmente para decidir si es un secreto real o un falso positivo (por ejemplo un valor de ejemplo). **Nunca pegar el valor en el chat ni en un commit.**

## Phase 5: Diff review

```bash
git diff --stat
git diff HEAD~1 --name-only 2>/dev/null || git diff --cached --name-only
```

Revisar cada archivo cambiado:
- ¿Hay cambios no intencionados?
- ¿Falta manejo de errores donde el brief lo exige?
- ¿Aparece algún secreto o valor hardcodeado?

## Phase 6: Contract tests — casos del DISENO.md vigente

Esta fase **no trae casos escritos**: se leen del `DISENO.md` actual, sea cual sea el reto. Si el reto cambia, cambian los casos sin tocar esta skill.

### 6.1 Armar el archivo de casos

1. Abrir `DISENO.md` y ubicar la tabla o lista de casos de prueba (suele llamarse "Plan de medición"). Abrir también `BRIEF.md` para la forma exacta de las peticiones y respuestas.
2. Escribir **una línea JSON por caso** en un archivo temporal **fuera del repo** (no se commitea). Mismos ids y mismo orden que `DISENO.md`. Formato:

```json
{"id": "<id del caso>", "method": "POST", "path": "<ruta>", "headers": {"<cabecera de auth>": "$TOKEN"}, "body": {"<según BRIEF.md>": "..."}, "expect_http": 200, "expect_body": {"<según la fila>": "..."}}
```

Reglas para traducir cada fila:
- **No inventar ni quitar casos, ni copiar valores de memoria**: todo sale de la fila de `DISENO.md` y del contrato de `BRIEF.md`.
- **El nombre de la cabecera de autenticación, las rutas, los formatos y el límite de tiempo salen siempre de `BRIEF.md`**. Esta skill no fija ninguno; si el brief no los define, preguntar al usuario.
- `expect_http`: el que diga la fila; si no lo dice, el que fije el contrato del brief para ese tipo de resultado. Si no se puede saber, preguntar al usuario.
- `expect_body`: basta que cada clave esperada exista con ese valor (el cuerpo real puede traer más campos). Pero un `{}` esperado exige `{}` exacto: si la fila dice `answer: {}`, escribir `"answer": {}` y el corredor fallará si llega cualquier dato ahí. Sin `expect_body`, el cuerpo no se compara.
- Token válido: `"$TOKEN"` (el corredor lo toma de la variable de entorno `EVAL_TOKEN`). Token incorrecto: un valor falso cualquiera. Sin token: omitir la cabecera.
- JSON roto o campo faltante: usar `raw_body` o un `body` incompleto, según la fila.
- Si la fila aún dice "por medir" o no tiene valor esperado, ese caso **no se puede verificar**: reportarlo como NO VERIFICABLE, nunca como correcto.

### 6.2 Correr contra la URL local Y la pública

1. Levantar el servidor local con el comando del proyecto (según README; por ejemplo `uvicorn app.main:app --port 8000`).
2. Tener `EVAL_TOKEN` ya cargado en el entorno de la terminal. No escribir ni mostrar su valor.
3. La URL pública la da el usuario (o está en README/BRIEF). Si todavía no hay despliegue, correr solo local y reportar **"pública: NO PROBADA"**; no darla por buena.

```bash
python3 -I .claude/skills/verification-loop/run_cases.py <archivo-de-casos.jsonl> \
  --base http://localhost:8000 \
  --base <URL-pública> \
  --max-seconds <límite por caso del BRIEF.md>
```

`--max-seconds` viene del `BRIEF.md`. Un caso que tarde más se marca FAIL, y cada petición espera como máximo ese valor + 5 s. Si el brief no fija límite, omitir la opción: cada petición espera hasta 120 s y el tiempo solo se muestra, no se juzga.

### 6.3 Qué debe mostrar la salida

Para **cada** caso y **cada** URL: código HTTP recibido contra esperado, cuerpo recibido contra esperado, tiempo en segundos y PASS/FAIL. El código HTTP se muestra siempre, también en los casos que pasan (200, 400, 401…).

Si un caso pasa en local y falla en la URL pública, la causa suele estar en el despliegue (proxy HTTPS, variable de entorno distinta, catálogo sin cargar), no en el código.

## Reporte final

```
VERIFICATION REPORT
===================
Tools:     [OK / instaladas ahora: ...]
Lint:      [PASS/FAIL] (X errores)
Types:     [PASS/FAIL] (X errores)
Tests:     [PASS/FAIL] (X/Y pasaron)
Security:  [PASS/FAIL] (archivos con posible secreto: X, .env fuera de git: sí/no)
Diff:      [X archivos cambiados]
Contracts: local X/N · pública X/N (o "NO PROBADA") · no verificables: X

Overall: [LISTO / NO LISTO] para push
```
