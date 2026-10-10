# Bitácora de cambios — sábado 10 de octubre

Qué falló, por qué, qué se cambió y qué se midió antes y después. Se actualiza con cada commit.

**Cómo leerla**
- **Medido** = lo corrí y vi el resultado. **Estimado** = cálculo mío, no medido.
- Los tiempos y costos de una sola corrida pueden variar de una corrida a otra (la IA no responde igual dos veces).
- "Escritorio" es la pantalla remota de práctica; "banco" es `bench.py`.

---

## Resumen de corridas (todas medidas, en local salvo que diga "publicado")

| # | Código | E1 | E2 | E3 | E4 | E5 |
|---|--------|----|----|----|----|----|
| 1 | `c5af0e4`+ciclo | **falló** 46 s, 4 pasos | | | | |
| 2 | `aa406dd` | pasó 106 s, 13 pasos, US$0.040 | | | | |
| 3 | `aa406dd` | | pasó 203 s, 19 pasos, US$0.092 | **falló** 273 s (tope de tiempo) | **falló** 282 s (tope de tiempo) | pasó 49 s, 6 pasos, US$0.021 |
| 4 | `7a1a611` | pasó 91 s, 11 pasos | sin veredicto (`/__check` cortó la conexión) | **falló** 134 s (error de formato) | pasó 109 s, 11 pasos | |
| 5 | `b389fba` | pasó 85 s, 11 pasos, US$0.033 | pasó 70 s, 9 pasos, US$0.029 | **falló**: respondió 16, era 45 | **falló** (error de formato) | |
| 6 | `8673f92` | pasó 109 s, 13 pasos, US$0.046 | pasó 76 s, 9 pasos, US$0.033 | **falló**: respondió 51, era 45 | pasó 88 s, 10 pasos, US$0.044 | |
| 7 | nota (este día) | | | _pendiente_ | | _pendiente_ |

Publicado en `frontier.jutilabs.com` (servidor con versiones anteriores a las del repo):
E1 pasó 103 s · luego una corrida con `ReadTimeout` sin causa clara · luego dos E1 fallidos (ver cambio 12).

---

## Cambios, en orden

### 0. Revisión rápida inicial
- **Modelos:** `google/gemini-3.8-flash` y `qwen/qwen3.8-flash` existen en OpenRouter (lista de 458 modelos). Medido.
- **Tesseract:** no estaba instalado en la Mac. Se instaló la versión 5.5.3 con español (`spa`). Medido.
- **Secretos:** `.env` y `logs/` ya estaban en `.gitignore`; `.env` nunca estuvo en git; la búsqueda de secretos en todos los archivos del repo dio 0 coincidencias. Medido.

### 1. Esqueleto con `/health` protegido — `49be449`
- **Qué:** servicio con `GET /health` que exige el token del equipo, y Dockerfile con Tesseract en español.
- **Medido:** sin token → 401; token correcto → 200; token malo → 401.

### 2. Cliente VNC y lectura de pantalla — `0627628`
- **Qué:** cliente VNC propio (limpio a partir del spike) y lectura de textos con Tesseract.
- **Decisión con datos:** leer la captura ampliada al doble. Encontró 9 de 10 textos esperados en una tabla densa (1x: 8 de 10) y 8 de 9 en un formulario (1x: 6 de 9). Medido sobre capturas guardadas.
- **Tiempos medidos:** conexión 0.9–1.9 s; esperar pantalla quieta ~2.2 s; leer textos 0.55 s (formulario) a 1.6 s (tabla densa).

### 3. IA con formato fijo y costo real — `c5af0e4`
- **Qué:** la IA responde en un formato fijo validado; el costo de cada llamada se lee de `usage.cost`, sin precios escritos a mano; la contraseña nunca entra al prompt.
- **Prueba suelta (una llamada con una pantalla inventada):** Gemini 3.8 Flash 7.3 s y US$0.0024; Qwen 3.8 Flash 4.75 s y US$0.0003. Es una sola llamada de cada uno: **no** es una comparación seria.

### 4. Ciclo del agente, banco y pruebas — `e5734a9`, `e8479af`, `ea9e260`
- **Qué:** ciclo mirar → decidir → supervisor → actuar; gestor de tareas con una tarea por escritorio; `bench.py`; `deploy.sh`; pruebas de contrato y de secretos.
- **Medido:** 21 pruebas pasan.

### 5. Primer E1: JSON cortado — `aa406dd`
- **Qué falló:** E1 falló en 46 s. El mensaje decía que la IA no devolvió el formato pedido.
- **Por qué:** el tope de salida (600 unidades) era corto y el modelo, al "pensar", cortaba la respuesta a la mitad.
- **Qué cambié:** tope de salida a 2000 y razonamiento bajo. Los dos se ajustan en `.env` (`LLM_MAX_TOKENS`, `LLM_REASONING_EFFORT`).
- **Antes → después (medido):** falló (46 s, 4 pasos, US$0.022) → pasó (106 s, 13 pasos, US$0.040).

### 6. E2–E5 con la primera versión (corrida 3)
- **Medido:** E2 pasó pero con 19 pasos; E3 y E4 se quedaron sin tiempo; E5 pasó (fallida como se esperaba, 49 s).
- **Diagnóstico con capturas y bitácoras:** ver el cambio 7.

### 7. Lectura de botones — `a16059d`, `cf9984b`
- **Qué falló (medido en las bitácoras):**
  1. Tesseract no leía el texto blanco sobre azul de los botones. "Buscar" no apareció en **ningún** de los 26 pasos de E3; "Guardar" tampoco se leyó en E2.
  2. Dos botones pegados ("Nuevo pedido" y "Exportar") salían como un solo texto: pasó en 18 de los 28 pasos de E4 y el clic caía en "Nuevo pedido".
  3. Los números de la lista cambian en cada paso y la IA reusaba los viejos.
- **Por qué:** al leer la página entera, Tesseract no encuentra el texto blanco sobre azul; leído **recortado y solo**, el botón sí sale ("Guardar" salió leído bien). Y yo unía palabras cercanas sin respetar los bordes de los botones.
- **Qué cambié:** se detectan los rectángulos azules por color y se leen recortados; los bordes `|` y `[ ]` separan textos; una línea nueva en las instrucciones de la IA avisa que los números cambian en cada paso. Se apaga con `OCR_BOTONES=false`.
- **Antes → después (medido):**
  - Sobre 7 capturas guardadas, "Buscar" y "Guardar" aparecen donde antes no, con +0.1 s por paso.
  - E2: 19 pasos y 202 s → 9 pasos y 70–76 s.
  - E4: falló (28 pasos, 282 s) → pasó (88–109 s).
- **Intentos descartados (no quedaron en el código):**
  - Segunda lectura de toda la página con la imagen invertida: no recuperó ningún botón.
  - Detector general de botones grises por color: **empeoró** la lectura (se confundía con las franjas de las tablas y metía basura) y duplicaba el tiempo. Revertido antes de usarlo.

### 8. `deploy.sh` con los valores del servidor — `bbeee9f`
- **Qué falló:** la comprobación de `/health` falló "por apuro" aunque el servicio estaba bien.
- **Por qué:** `curl --retry` no reintenta cuando la conexión se corta (error 56).
- **Qué cambié:** valores por defecto del servidor (`frontier-api`, red `jutilabs_default`, puerto `8010`) y un bucle propio de hasta 40 intentos.
- **Medido:** contra un servidor falso que cortaba la conexión 4 s, el `--retry` viejo falló con el error 56 y el bucle nuevo respondió en el intento 5. `deploy.sh` entero no se pudo correr en la Mac (Docker apagado); solo se probó el bucle.

### 9. Una razón larga tumbaba la tarea — `c2e63c1`
- **Qué falló:** E3 se cayó con "la IA no devolvió el formato pedido: la razón supera 300 caracteres".
- **Por qué:** error mío: el campo `razon` solo sirve para la bitácora y lo estaba validando como si fuera esencial.
- **Qué cambié:** si la razón viene larga, se recorta; nunca se rechaza la decisión por eso.
- **Medido:** prueba nueva (razón de 900 caracteres → queda en 300 y la acción se acepta).

### 10. `/__check` cortaba la conexión — `b389fba`
- **Qué falló:** E2 salió "FALLÓ" con `RemoteProtocolError` en `/__check`, aunque el agente había terminado en 9 pasos.
- **Por qué:** el escritorio cortó la conexión de esa llamada; es del lado del escritorio, no del agente.
- **Qué cambié:** el banco reintenta `/__check` hasta 3 veces y deja los reintentos como aviso.
- **Nota:** el veredicto real de ese E2 se perdió (el estado se reseteó para E3). Quedó **sin veredicto**, no como éxito.

### 11. Medir en qué se va el tiempo — `04f6675`
- **Qué:** el agente ahora cuenta segundos de pantalla, lectura de textos, IA y acciones; `bench.py` los muestra.
- **Medido (corrida 5):** la IA es el 56–71 % del tiempo (~4.5 s por llamada en E1–E3, 9 s en E4); esperar pantalla 15–25 % (~1.9 s por paso); leer textos 7–10 %; acciones 3–7 %.

### 12. Una respuesta de la IA con formato inválido ya no mata la tarea — `c26ea92`
- **Qué falló:** E4 (local) y dos E1 (publicado) terminaron en `fallida` porque la IA mandó una vez un objeto inválido ("clic sin número", "escribir sin texto").
- **Por qué:** mi código daba la tarea por perdida al primer error de formato.
- **Qué cambié:** el ciclo reintenta hasta 3 veces seguidas, avisando a la IA qué estaba mal, sin tocar la pantalla.
- **Medido:** 4 pruebas nuevas con un escritorio y una IA de mentira (reintenta y sigue; 3 seguidos → `fallida`; nunca toca el escritorio al fallar).
- **No medido contra el escritorio real:** E4 pasó en la corrida 6 sin que haya vuelto a salir el error, pero no sé si el reintento se activó.

### 13. El `ReadTimeout` — sin explicar del todo
- **Qué se vio:** el banco se cayó con `ReadTimeout` al correr E1 contra el servicio publicado.
- **Qué medí:**
  - `POST /tasks`, 17 llamadas contra el publicado: todas HTTP 200 y menos de 2 s. En reposo: mediana 342 ms, máximo 968 ms. Con una tarea real corriendo: mediana 353 ms, máximo **1655 ms** (poco margen).
  - Con el banco ya instrumentado, el timeout fue en `GET /tasks/{id}` (15 s) y en otra corrida en `GET /tasks/{id}/detalle` (con la tarea terminada). **Nunca en `POST /tasks`.**
- **Mi error:** en una corrida mandé 10 tareas-sonda extra al servidor y deformé ese resultado. La repetí limpia.
- **Diagnóstico del servidor (hecho por ti):** `OOMKilled=false`, 0 reinicios, 5.5 GB libres; los `GET /tasks` responden 200 cada ~3.4 s sin huecos de 15 s. **El cuelgue no está en el servidor.**
- **Estado:** causa no establecida. Hipótesis sin verificar: la red entre la Mac y el servidor. En local no se reprodujo.

### 14. Trabajo pesado fuera del ciclo principal — `b7b16e9`
- **Qué:** comparar capturas, codificar PNG y escribir la bitácora corren en hilos aparte; menos copias al armar la imagen. Es un seguro para el contrato de 2 s.
- **Medido (local, durante tareas reales):** unas 1 900 consultas a `/health` con mediana 4 ms y la más lenta 20 ms, 0 errores.
- **No medido:** no tengo una medición "antes", así que no puedo decir cuánto mejoró.

### 15. `Ctrl+A` solo en cajas de texto — `6fb49b6`
- **Qué falló:** `Ctrl+A` con el foco en un desplegable selecciona toda la página y la resalta; eso empeoraba la lectura (se vio en E3).
- **Qué cambié:** la IA declara `campo = texto | lista`; en listas no se pulsa `Ctrl+A`. Por defecto sigue siendo texto.
- **Medido:** E1–E4 siguen pasando con el cambio; el efecto aislado sobre la lectura **no** se midió.

### 16. Anti falso éxito en conteos — `d48ce03`
- **Qué falló:** E3 respondió "16" y reportó `terminada` (el correcto era 45): contó una sola página.
- **Qué cambié (regla del DISENO: nunca "terminada" si no quedó bien):** en preguntas de conteo no se permite `terminada` si hay paginación sin recorrer o si el número no coincide con un total que muestre el programa. Tras 2 avisos pasa a `fallida` explicando por qué, sin línea `respuesta:`.
- **Medido:** 7 pruebas nuevas.
- **Límite:** no detecta un conteo mal hecho cuando sí se recorrieron todas las páginas (ver el cambio 18).

### 17. Botones grises que no se leen: `clic_zona` — `6fb49b6`, `8673f92`
- **Qué falló:** "Siguiente", "Anterior" y "Limpiar" (grises con borde) no salen en la lectura de la página. E3 no podía cambiar de página.
- **Por qué:** igual que con los azules: Tesseract los lee recortados, no en la página.
- **Qué cambié:** la IA, que ve la captura, indica el botón y su zona aproximada (`clic_zona`); el código busca en esa zona las manchas del tamaño de un botón y lee, recortadas, las más cercanas.
- **Intentos que no sirvieron:** leer la zona con Tesseract tal cual → 4 de 40; búsqueda por color → 8 de 64 (error mío de desbordamiento y las caras de los botones tienen degradado, no un color liso).
- **Antes → después (medido, 64 búsquedas con la IA "equivocándose" hasta 80 px):** 8 de 64 → **64 de 64**, 0 clics en lugar equivocado, error de 0–2 px, 0.08 s de mediana.
- **En vivo:** en E3 la IA lo usó 5 veces y las 5 encontró "Siguiente"; por primera vez recorrió las 3 páginas.

### 18. El conteo de E3 sigue mal: nombre parecido y falta de memoria — este commit
- **Qué falló:** E3 recorrió las 3 páginas y respondió **51** en vez de **45**.
- **Por qué (diagnóstico de la bitácora):** contó 20 + 20 + 11 filas, y entre ellas hay filas de "Ferretería Ruiz **e Hijos**" (6). El filtro del programa busca partes del texto, así que las trae. La regla "elige solo el exacto" se le olvidó entre páginas, porque la IA no tiene memoria entre pasos más que la lista de acciones.
- **Qué cambié:**
  1. Campo `nota`: un apunte corto que la IA escribe en cualquier paso y que se le devuelve en cada paso siguiente bajo "TUS NOTAS" (las últimas 12, hasta 400 caracteres cada una; las notas largas se recortan y se filtran los secretos).
  2. Instrucción de contar **solo** las filas cuyo nombre sea exactamente el pedido, anotar "Página K: X exactas de Y (descarté Z)" y sumar las notas de todas las páginas.
- **Medido:** 47 pruebas pasan (2 nuevas: las notas vuelven en el paso siguiente; la nota larga se recorta y no filtra secretos).
- **Resultado en el escritorio real:** _pendiente (ver corrida 7)_.

---

## Riesgos y pendientes conocidos
- `ReadTimeout` contra el publicado: sin causa establecida (cambio 13).
- La IA es lo más lento (5 s por llamada o más). Secuencias de varias acciones por decisión quedan **para después del imprevisto**.
- Lo publicado en el servidor está **detrás** del repo: falta `git pull && ./deploy.sh` cuando decidas publicar.
- El efecto de `Ctrl+A` en listas y de los hilos aparte no se aisló con medición.
