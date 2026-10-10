# Agente que opera programas sin API (Frontier BOG/26 · Reto 1)

Un "empleado digital": recibe una orden en español, mira la pantalla de un computador remoto por VNC, hace
clics y escribe como una persona, y al final reporta `terminada` o `fallida` con un resumen.
Servicio publicado: <https://frontier.jutilabs.com> · Diseño: [DISENO.md](DISENO.md) ·
Bitácora de cambios y mediciones: [BITACORA.md](BITACORA.md) · Diagrama: [docs/DIAGRAMA.png](docs/DIAGRAMA.png)

## Qué hace (contrato, ver BRIEF.md)
Todas las rutas exigen `Authorization: Bearer <TEAM_TOKEN>`.

| Ruta | Para qué |
|---|---|
| `GET /health` | Responde `{"ok": true}` cuando está listo |
| `POST /tasks` | Recibe `{"tarea": "...", "escritorio": {"url": "wss://.../websockify", "password": "..."}}` y responde `{"task_id": "..."}` enseguida |
| `GET /tasks/{task_id}` | Responde `{"estado": "en_curso" \| "terminada" \| "fallida", "resumen": "..."}` |

Una sola tarea activa por escritorio (si llega otra, la anterior se detiene). Topes por tarea: 270 s y
US$0.15 (configurables).

## Requisitos
- Python 3.12
- Tesseract 5 **con el idioma español**: Mac `brew install tesseract tesseract-lang`; Debian/Ubuntu
  `apt install tesseract-ocr tesseract-ocr-spa`
- Una llave de OpenRouter (la IA) y, para el banco de pruebas, la tarjeta del escritorio de práctica
  (URL, contraseña y token de `/evento`).

## Instalar
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # incluye requirements.txt, pytest y ruff
cp .env.example .env                              # y completa los valores vacíos (ver abajo)
```
Qué llenar en `.env` (nunca se sube al repo): `TEAM_TOKEN` (el token del equipo),
`OPENROUTER_API_KEY`, `OPENROUTER_BUDGET_USD` y, solo para `bench.py`, `DESKTOP_URL`,
`DESKTOP_PASSWORD`, `DESKTOP_TOKEN`. El resto trae valores por defecto: modelo (`LLM_MODEL`), esperas,
duración del clic, topes. Si la app cambia, se ajusta ahí, sin tocar código.

## Levantar el servicio en local
```bash
.venv/bin/uvicorn app.main:crear_app --factory --host 127.0.0.1 --port 8000
curl -H "Authorization: Bearer <TEAM_TOKEN>" http://127.0.0.1:8000/health      # {"ok":true}
```
Sin token responde 401.

## Probar
```bash
.venv/bin/pytest                               # 93 pruebas (contrato, secretos, ciclos, conteos, reconexión...)
.venv/bin/python bench.py --casos E1           # un caso real: reset -> agente -> /__check -> tabla
.venv/bin/python bench.py                      # los 5 casos de pruebas/
.venv/bin/python bench.py --modelo qwen/qwen3.8-flash    # comparar modelos (servicio local)
.venv/bin/python bench.py --base https://frontier.jutilabs.com   # contra el publicado
```
`bench.py` usa SU escritorio de práctica (el de `.env`) y muestra, por caso: si pasó, tiempo, costo,
pasos y en qué se va el tiempo (pantalla / lectura de textos / IA / acciones).

## Publicar (en el servidor, dentro de la carpeta del proyecto con su `.env`)
```bash
./deploy.sh     # git pull + docker build + reemplaza el contenedor + comprueba /health
```
Valores por defecto de `deploy.sh`: contenedor `frontier-api`, red `jutilabs_default`, puerto
`127.0.0.1:8010` (Caddy apunta a `frontier-api:8000`). Ojo: el `.env` se lee **al crear** el contenedor.
Para el servidor se agregó `OMP_THREAD_LIMIT=1` (ver BITACORA.md, cambio 9 y 11).

## Mapa del código (`app/`)
| Archivo | Qué hace |
|---|---|
| `main.py` | Las rutas y el token |
| `tasks.py` | Gestor de tareas: una por escritorio, topes de tiempo y de costo, estados |
| `agent.py` | El ciclo mirar → decidir → supervisor → actuar; reconexión; notas |
| `supervisor.py` | Reglas en código: ciclos, guardar una sola vez, conteos, confirmaciones, teclas |
| `llm.py` | La IA por OpenRouter, formato fijo y las instrucciones (prompt) |
| `screen.py` | Capturar, esperar a que la pantalla quede quieta y leer textos y botones con Tesseract |
| `vnc.py` | Cliente VNC propio (RFB sobre websocket), clic de 150 ms, teclas, reconexión |
| `secretos.py` | Filtro: la contraseña y las llaves nunca salen en el resumen, la IA ni la bitácora |
| `bitacora.py` | Por tarea: cada paso con su captura y su decisión, en `logs/` |
| `config.py` | Toda la configuración sale de `.env` |

Otras carpetas: `tests/` (pruebas y capturas reales de muestra), `pruebas/` (los 5 casos oficiales),
`spike/` (la prueba de conexión del primer día; histórica), `.claude/` (kit genérico de trabajo; su
`verification-loop/run_cases.py` es de otro reto y **no se usa**: aquí el banco es `bench.py`).

## Estado publicado
El servidor corre `f6f831a` (deploy de las 18:28, "Listo", confirmado por el equipo), que incluye la regla
de listas desplegables. Comprobarlo con `git log --oneline -1` en el servidor.

## Lo que NO se construyó del diseño
Las capas 2 y 3 de [DISENO.md](DISENO.md) (habilidades generales sin IA y procedimientos aprendidos por
programa) **no existen**: hoy cada paso lo decide la IA, con un supervisor de reglas en código. Por eso la
meta "% de pasos sin IA" no se puede medir. El punto de enchufe está en `Agente.decidir`.

## Límites conocidos (honestos)
- **Nombres del caso E3 dentro del prompt:** las instrucciones traen como ejemplo "Ferretería Ruiz /
  Ferretería Ruiz e Hijos" (el caso de práctica). Es dato de la app de práctica metido en el código; la
  prueba que busca la palabra de la app no lo detecta.
- **`Esc` está bloqueada para cualquier app** (`supervisor.py`, lista `TECLAS_BLOQUEADAS`). En otra app
  puede ser la forma de cerrar un modal y el código la rechaza antes de que la IA lo intente.
- **No hubo tiempo de medir la versión final completa en el servidor.** La mayoría de las cifras se midieron
  en una Mac de 10 núcleos contra el escritorio de práctica; en el servidor solo se midió la lectura de
  pantalla y una parte del set oculto (ver BITACORA.md, cambio 11).
- **"Terminada" es lo que reporta el agente, no la nota del evaluador.** Hubo "terminada" con un conteo
  equivocado (E3: 16, 51, 44, 43). E3 es el caso más inestable.
- La IA es lo más lento (~5 s por llamada); una secuencia de varias acciones por decisión no se hizo.
- Los casos propios del diseño (13 en total) no se crearon: solo existen los 5 oficiales.
