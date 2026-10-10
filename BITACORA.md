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
| 7 | `2bc0e1a` (nota) | | | pasó 100 s, 10 pasos, US$0.063 · pasó 100 s, 10 pasos, US$0.053 · **falló** 133 s: respondió 44, era 45 | | pasó 52 s, 6 pasos, US$0.024 |
| 8 | `2bc0e1a` (control) | pasó 109 s, 13 pasos, US$0.048 | pasó 85 s, 9 pasos, US$0.034 | | pasó 82 s, 10 pasos, US$0.045 | |

| 9 | `fd239c9` (tema **viejo**, tras el aviso del incidente) | pasó 97 s, 13 pasos, US$0.047 | pasó 67 s, 9 pasos, US$0.034 | pasó 112 s, 11 pasos, US$0.074 | pasó 82 s, 11 pasos, US$0.050 | pasó 42 s, 6 pasos, US$0.024 |

| 10 | `ec46b68` — **tema nuevo v4.2, ANTES de adaptar** | pasó 112 s, 16 pasos, US$0.058 | pasó 103 s, 13 pasos, US$0.051 | pasó 100 s, 11 pasos, US$0.066 | pasó 100 s, 13 pasos, US$0.059 | pasó 61 s, 9 pasos, US$0.034 |
| 11 | `843cc5b` (mouse estacionado: **regresión mía**) | **falló** 273 s, 28 pasos | **falló** 106 s, 13 pasos | pasó 133 s, 12 pasos | **falló** 273 s, 35 pasos | **falló** 112 s, 15 pasos |
| 12 | `29a34de` — **tema nuevo v4.2, DESPUÉS de adaptar** | pasó 118 s, 14 pasos, US$0.057 | pasó 85 s, 10 pasos, US$0.042 | **falló** 115 s: respondió 43, era 45 | pasó 124 s, 11 pasos, US$0.053 | pasó 79 s, 7 pasos, US$0.030 |
| 13 | `29a34de` (E3 repetido) | | | pasó 118 s · **falló** 103 s (43 otra vez) | | |
| 14 | opción A (códigos de fila en la nota), E3 ×3 | | | pasó 97 s · pasó 109 s · pasó 97 s (45, 45, 45) | | |
| 15 | opción A, los 5 casos | pasó 127 s, 16 pasos, US$0.067 | pasó 85 s, 10 pasos, US$0.043 | pasó 100 s, 11 pasos, US$0.060 | pasó 97 s, 11 pasos, US$0.054 | pasó 55 s, 7 pasos, US$0.029 |
| 16 | regla anti-ciclo, los 5 casos | pasó 130 s, 15 pasos | pasó 100 s, 10 pasos | **falló** 106 s: respondió 16 ("única página") | **falló** 52 s: `ConnectionClosedError` | pasó 61 s, 7 pasos |
| 17 | regla anti-ciclo, repeticiones | | | pasó 92 s · pasó 96 s · pasó 99 s (45 las tres) | pasó 104 s | |
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
- **Resultado en el escritorio real (medido, E3 tres veces):** pasó, pasó, falló.
  - Las dos que pasaron lo hicieron por la razón correcta: notas "página 1: 16 exactas de 20 (descarté 4) · página 2: 18 exactas de 20 (descarté 2) · página 3: 11 exactas de 11" → total **45**, y el resumen dice que descartó 6 filas de "e Hijos". 10 pasos, 100 s.
  - La que falló respondió **44**: en la página 1 contó "15 exactas de **19** filas" cuando la página tiene 20 (se saltó una fila al contarla). Las páginas 2 y 3 salieron bien. Reportó `terminada`: sigue siendo un falso éxito, ahora por 1.
  - Antes de la nota: 16 (una página) y 51 (con "e Hijos"). Con la nota: 45, 45 y 44.
- **Control de que nada se rompió (medido, corrida 8):** con el prompt nuevo, E1, E2 y E4 pasan (109 s, 85 s y 82 s).
- **E5 (medido, no se había corrido desde los cambios):** pasó, `fallida` como se espera, 52 s, 6 pasos, US$0.024.
- **Idea para cerrar el caso del 44 (NO hecha, a tu decisión):** las páginas completas de una lista tienen todas el mismo número de filas. Si las notas dicen "19 filas" en la página 1 y "20" en la 2, el supervisor puede pedir recontar antes de dar `terminada`. Estimo 20–25 min; costaría ~40 s más en esos casos.

---

## Incidente de las 15:30 — el tema de la app cambió (paso 1: DETECTAR, sin tocar código)

**Lo que se nos dijo:** la app de pruebas cambió de tema: botones movidos, etiquetas distintas y un
modal nuevo al abrir la app. La evaluación oculta corre sobre el tema nuevo.

**Cómo lo buscamos (todo de solo lectura, sin cambiar código):**
1. Reset del escritorio + captura + lectura de textos (a las 15:38 y otra vez a las 15:46).
2. E1–E5 completos con el código tal como estaba (`fd239c9`).
3. Comparación pantalla a pantalla entre esta mañana y ahora: textos de la primera pantalla de cada caso,
   píxeles del formulario "Nuevo cliente", y **posición de cada etiqueta** en Clientes, Facturas, Pedidos
   y barra de menú.
4. Abrir cada menú de la barra (Archivo, Comercial, Cartera, Herramientas, Ayuda) en busca de modales.

**Qué se midió (todo medido):**
- **E1–E5: 5 de 5 pasaron** (tabla, corrida 9). Costo total US$0.23; 7.1–10.2 s por paso.
- **Modal:** no aparece. Ni tras el reset, ni 6 s después, ni al abrir los 5 menús.
- **Etiquetas movidas:** **0 de 24** comparadas (menú 5, Clientes 7, Facturas 6, Pedidos 6) están a más de 6 px de donde estaban.
- **Formulario "Nuevo cliente":** 0.01 % de píxeles distintos (solo el cursor del mouse).
- **Pantalla de inicio:** 0.15 % de píxeles distintos. La única diferencia es el título de la página: dice
  el nombre del último módulo visitado ("Pedidos" a las 15:38, "Clientes" a las 15:46). Esa pantalla ya se
  veía así en las corridas de esta mañana (aparece en la bitácora de la primera corrida), así que
  **no** es parte del cambio de tema.
- Encabezado igual: "SIGECOM · Distribuidora Andina v3.9", mismo usuario y fecha.

**Conclusión honesta:** en el escritorio de práctica (`DESKTOP_URL` de mi `.env`) **no se ve ningún cambio de
tema**. No puedo confirmar el modal ni decir qué dice, porque no lo he visto. Lo que sí sé es que el código
actual pasa los 5 casos sobre lo que tengo delante. Posibles explicaciones, **sin verificar**:
- El tema nuevo solo existe en los escritorios de evaluación, no en el de práctica.
- El escritorio de práctica cambia más tarde (después de las 15:30–16:00).
- Existe un escritorio nuevo (otra URL/contraseña en la tarjeta de `/evento`) y mi `.env` apunta al viejo.

**Qué falló:** nada en las corridas. El riesgo no está en lo que falló sino en lo que no podemos ver.

**Qué partes del código dependen del tema (de la lectura del código, no de una corrida):**

| Dónde | Qué asume | Qué pasa si el tema cambia |
|---|---|---|
| `app/screen.py:250` | Botones primarios = fondo oscuro con más azul que rojo (texto blanco) | Un botón verde, rojo o con texto oscuro sobre claro **no** se detecta y queda sin leer |
| `app/screen.py:235` | Un botón mide 28–260 px de ancho y 20–60 de alto, y está relleno más del 45 % | Botones más altos, más bajos o muy anchos se descartan |
| `app/screen.py:307-319` | Cara del botón = uno de los 12 colores más frecuentes de la zona, tolerancia ±14, 120 px mínimo | Botones con degradado fuerte, sombra o borde grueso pueden no separarse |
| `app/screen.py:29,119,26-27` | Máx. 12 botones leídos; bordes `\|[]{}()`; hueco entre palabras 1.2 alturas; confianza 30 | Otra fuente o tamaño cambia cómo se agrupan y se leen los textos |
| `.env` `OCR_SCALE=2` | Ampliar 2x lee mejor (medido con esta fuente) | Otra tipografía podría leerse mejor a 3x |
| `.env` `FIELD_OFFSET_Y=18`, `X=25` | El campo está ~18 px **debajo** de su etiqueta (o 25 px a la derecha) | Con etiquetas a la izquierda o más espacio, el clic cae fuera del campo |
| `app/screen.py:22-24`, `.env` `SCREEN_STABLE_DIFF=0.01` | Un cambio real mueve más de 20 píxeles con diferencia > 24 | Un tema de bajo contraste puede parecer "sin cambio" |
| `app/llm.py:70-71,122,137` | Pantalla de 1280×800 fija | Otra resolución rechaza `clic_zona` |
| `app/llm.py` (instrucciones) | Palabras de la app de práctica: "Volver", "Guardar", "Buscar", "Siguiente", "Dato inválido", cartel de F12 con "OK", flecha ▼ | Con etiquetas distintas ("Cancelar", "Aceptar", "Next") la IA recibe instrucciones con palabras que no existen |
| `app/supervisor.py:14` | `Ctrl+L`, `F12` y `Esc` están bloqueadas | En un tema/kiosco distinto esas teclas podrían servir (o no) |
| `app/supervisor.py:16-27` | Palabras de error, de paginación ("Página K", "Siguiente") y de totales ("N registros") | Etiquetas distintas no se reconocen: la regla anti falso éxito no se activa |
| `.env` `CLICK_HOLD_MS=150` | La app ignora clics de menos de 100 ms | Otra app podría necesitar más tiempo |
| **Modales** | No hay ninguna regla específica; depende de que la IA lo vea en la captura y lo cierre | Un modal que tapa la app al abrir puede consumir pasos o confundir la lista de textos |

**Lo que NO depende del tema:** el cliente VNC y su autenticación, el ciclo mirar-decidir-actuar, los
topes de tiempo y de gasto, el filtro de secretos, la bitácora, las notas y la regla de conteos
(salvo por las palabras de la fila "supervisor").

**Qué se puede ajustar sin tocar código (en `.env`):** `LLM_MODEL`, `LLM_REASONING_EFFORT`, `LLM_SEND_IMAGE`,
`OCR_SCALE`, `OCR_BOTONES`, `FIELD_OFFSET_X/Y`, `CLICK_HOLD_MS`, `SCREEN_*`, `TASK_MAX_SECONDS`.

**Estado:** esta sección es de las 15:38–15:46 (tema todavía viejo). La continuación, con el tema nuevo, está abajo.

---

## Incidente (tema nuevo v4.2): detectar, mirar, adaptar y medir

**Cómo se detectó el cambio.** A las 15:38–15:46 el escritorio de práctica seguía en el tema viejo (0 de 24
etiquetas movidas, sin modal). A las 15:58, después de que confirmaste el ticket, el reset dejó el
escritorio en **SIGECOM v4.2**: encabezado verde en vez de azul marino y un modal "Novedades de la
versión 4.2" con el botón verde "Entendido" y una ×. El modal dice: *los formularios ahora se aplican sin
cerrarse, la barra de acciones pasó a la derecha y hay nombres nuevos en los botones*.

### 1) ANTES: el código sin tocar, sobre el tema nuevo (corrida 10, medido)
**5 de 5 pasaron**, pero con más pasos que en el tema viejo (16/13/11/13/9 contra 13/9/11/11/6) porque el
primer paso siempre era el modal y a veces costó 2–3 pasos cerrarlo. No hubo ningún fallo. Lo que sí se vio
en las bitácoras (con captura):
- **Modal:** el agente lo cerró, pero en E2, E4 y E5 gastó 3 pasos. La IA dio la zona de "Entendido" como
  (656, 604): son coordenadas **normalizadas a 1000** (el botón real está en (841, 483)); el sistema las
  tomó como píxeles y no encontró nada. Además "Entendido" se leía "EXI" o "Eutendido".
- **Botones leídos mal o nada:** en Facturas, Filtrar/Limpiar/Exportar/Siguiente/Anterior no salían en la
  lista de textos; en Clientes salía fusionado "Exportar Ml Crear cliente".
- **El cursor del mouse** queda encima del botón pulsado y tapa letras: "Filtrar" salía "Filtuar".

### 2) MIRAR: cómo quedó el tema nuevo (capturas de las bitácoras, medido)
| Qué | Tema viejo | Tema nuevo (v4.2) |
|---|---|---|
| Versión / encabezado | v3.9, azul marino (31, 59, 99) | **v4.2, verde oscuro (45, 74, 62)** |
| Modal al abrir | no hay | **"Novedades de la versión 4.2"**, botón verde "Entendido" (841, 483) y × |
| Botón principal | azul (82, 125, 188) con texto blanco | **verde (80, 153, 118)** con texto blanco |
| Botón secundario | gris claro con borde | igual (gris (247, 248, 250) con borde) |
| Buscar en listas | "Buscar" (azul) | **"Filtrar"** (verde) |
| Crear | "Nuevo cliente" / "Nuevo pedido" (a la izquierda) | **"Crear cliente" / "Crear pedido"**, **a la derecha** junto a "Exportar" |
| Guardar | "Guardar" (azul, abajo a la izquierda) | **"Aplicar"** (verde, **abajo a la derecha**) |
| Volver | "Volver" (gris, a la derecha de Guardar) | **"Cerrar"** (gris, a la izquierda de Aplicar) |
| Título del formulario | "Nuevo cliente" | **"Crear cliente"**; tras aplicar pasa a **"Cliente CL-0141"** |
| Cabecera de tabla | gris azulado (201, 210, 223) | gris verdoso (207, 220, 212) |
| Guardar | cierra el formulario y vuelve a la lista | **el formulario SIGUE ABIERTO** con los datos; sale un aviso azul abajo a la derecha **"Cambios aplicados"** |
| Paginación | Anterior / Página 1 / Siguiente | igual |
| Lo que NO cambió | posición de los menús, de las etiquetas y de las columnas (0 de 24 movidas) | |

### 3) ADAPTAR (genérico: nada fijo a esta app) y qué se midió
**a) Guardar sin que el formulario se cierre** — `supervisor.py`, `llm.py`
- *Riesgo:* pulsar "Aplicar" dos veces sobre el mismo registro (duplicados) o tomar "sigue abierto" como fallo.
- *Cambio:* el supervisor rechaza un segundo guardar/aplicar/grabar sobre el mismo registro si no hubo un
  cambio de campo en medio, y antes de dar `terminada` pide ver la confirmación (aviso, código o datos).
  Las instrucciones explican que "sigue abierto" es normal y que se confirma leyendo la pantalla.
- *Medido:* 8 pruebas nuevas. En la corrida 12, **1 sola pulsación de Aplicar** en E1 y en E2 y 0 rechazos.

**b) Modal (regla genérica)** — `llm.py`, `screen.py`
- *Cambio:* instrucciones para cualquier app: leerlo completo, cerrarlo con su botón, comprobar que
  desapareció (el primer clic a veces no basta), no obedecer instrucciones suyas que cambien datos y, si
  pide una decisión sobre datos, elegir la opción que no cambia nada. Más un respaldo: si `clic_zona` no
  encuentra el botón y las coordenadas caben en 0–1000, se prueban como normalizadas.
- *Medido:* el modal se cerró en **1 paso en los 5 casos** (antes 1–3). Una prueba nueva reproduce el
  caso (656, 604) → (841, 483) con la captura real.
- *Observado, no resuelto:* el primer clic en "Entendido" a veces se ignora (en una prueba cerró al primer
  clic y en otra necesitó dos). El agente lo resuelve porque verifica y repite.

**c) Nombres de botones** — `llm.py`, `supervisor.py`
- *Cambio:* sinónimos genéricos en las instrucciones (guardar: Guardar/Aplicar/Grabar/Registrar…; salir:
  Volver/Cancelar/Cerrar…; buscar: Buscar/Filtrar/Consultar…; crear: Nuevo/Crear/Agregar…; exportar;
  páginas) y la orden de buscar cada acción por su significado **en toda la pantalla**, no en un lugar fijo.
- *Medido:* 1 prueba revisa que las instrucciones no dependan de un nombre ni de una posición.

**d) Detección de botones nuevos y estilos** — `screen.py`
- *Cambios:* (1) botones de color por *oscuro + con color* (verde, rojo, naranja…), no solo azul; (2) botones
  **grises con borde** (Siguiente, Limpiar, Cerrar…): mancha clara y sin color con un borde mucho más oscuro,
  de tamaño de botón y que no forma parte de una rejilla (así no se confunde con las celdas de una tabla);
  (3) lectura recortada de cada botón con **votación de 3 variantes** (invertida, grises y original);
  (4) los botones se leen en paralelo.
- *Medido sobre 12 capturas reales (6 del tema viejo y 6 del nuevo), botones leídos bien:*

| | Antes | Después |
|---|---|---|
| Tema **viejo** | 14 de 20 (70 %) | **19 de 20 (95 %)** |
| Tema **nuevo** | 15 de 26 (58 %) | **26 de 26 (100 %)** |
| Total | 29 de 46 (63 %) | **45 de 46 (98 %)** |

  Falsos positivos: 0. Lo que "ya no sale" son lecturas basura ("ENS", "Filtuar", "Cin"). Costo: +0.1 a +0.35 s
  por pantalla en esta Mac (medido); en el servidor no se midió.

### 4) Dos regresiones mías, detectadas por la propia medición (honestidad para el debrief)
1. **Mouse estacionado → los submenús dejaron de abrir (corrida 11: 1 de 5).**
   - *Qué hice:* para que el cursor no tape letras, lo alejaba a una esquina tras cada clic.
   - *Qué falló:* el menú de 2.º nivel ("Maestros ▸") **se cierra al alejar el mouse**. Mi prueba solo
     había verificado el primer nivel ("Comercial") y la generalicé mal. El agente se quedó atascado
     (E1: 28 pasos, E4: 35 pasos).
   - *Prueba directa (medido):* mouse encima → submenú visible: **sí**; mouse en la esquina: **no**;
     mouse dentro del elemento: **no**.
   - *Qué cambié:* `PARK_MOUSE` queda **apagado** por defecto (opción en `.env`). Una prueba lo exige.
2. **El panel del menú desplegable se leía como un botón.** Mi detector de grises tomó el panel
   "Maestros ▸ / Ventas ▸" (208 × 55 px) como botón y lo leyó "AS". Ahora un botón gris mide como máximo
   36 px de alto y 200 de ancho, y una caja con varias líneas de texto dentro se descarta.
   Dos pruebas con la captura real del menú abierto lo cubren.
- *Por qué no se vio antes:* mis mediciones de botones eran sobre pantallas **sin menú abierto**. Quedó
  una muestra nueva (`nuevo_menu_abierto.png`) en `tests/fixtures/`.

### 5) DESPUÉS: la versión corregida sobre el tema nuevo (corrida 12, medido)

| Caso | ANTES (`ec46b68`) | DESPUÉS (`29a34de`) |
|---|---|---|
| E1 crear cliente | pasó · 112 s · 16 pasos · US$0.058 | pasó · 118 s · **14** pasos · US$0.057 |
| E2 corregir dirección | pasó · 103 s · 13 pasos · US$0.051 | pasó · **85 s** · **10** pasos · US$0.042 |
| E3 facturas vencidas | pasó · 100 s · 11 pasos · US$0.066 | **falló** · 115 s · 11 pasos · respondió **43**, era 45 |
| E4 exportar pedidos | pasó · 100 s · 13 pasos · US$0.059 | pasó · 124 s · **11** pasos · US$0.053 |
| E5 homónimos | pasó · 61 s · 9 pasos · US$0.034 | pasó · 79 s · **7** pasos · US$0.030 |
| **Pasaron** | **5 de 5** | **4 de 5** |
| Pasos (suma) | 62 | **53** (−15 %) |
| Tiempo (suma) | 476 s | 521 s (+9 %) |
| Costo (suma) | US$0.268 | **US$0.242** (−10 %) |

- **Menos pasos, pero más tiempo por paso** (de ~7–9 s a ~8–11 s): leer los botones recortados cuesta
  (leer textos: 39 s → 67 s en los 5 casos) y la IA tardó en promedio algo más.
- **E3 repetido con el código nuevo: 1 de 3** (pasó 118 s; falló dos veces con el **mismo 43**).
  - *Diagnóstico (medido):* la lectura de pantalla **no pierde filas**: la lista de textos trae los 20
    códigos por página en las tres corridas. Quien cuenta mal es la IA: en las dos corridas fallidas anotó
    "15 exactas de **19** filas" y "17 de **19**" cuando las páginas tienen 20; en la que pasó anotó 20 y 20.
    Descartó bien las 6 filas de "e Hijos" en las tres.
  - *No se puede atribuir al cambio de tema ni a mis cambios:* con el código anterior E3 había dado
    45, 45, 44, 51, 16… (2 de 3 antes de la nota; 1 de 1 en la corrida 10). Son pocas muestras.
- **Qué NO se pudo mejorar con medición:** la tasa de aciertos no subió (5/5 → 4/5, con E3 en su rango
  habitual de variación). Lo que sí subió es la lectura de botones (63 % → 98 %) y bajó el número de pasos.

### Qué parte del código depende del tema, después de este trabajo
| Dependencia | Estado |
|---|---|
| Botones de un solo color (azul) | **Arreglado:** cualquier fondo oscuro con color |
| Botones grises no leídos | **Arreglado:** detección por borde y forma, sin tablas |
| Palabras fijas en las instrucciones | **Arreglado:** sinónimos y búsqueda en toda la pantalla |
| Cursor tapando letras | **Mitigado** con votación; estacionarlo rompe los submenús (medido) |
| `FIELD_OFFSET_Y/X` (campo bajo la etiqueta) | Sin cambio; en v4.2 las etiquetas siguen encima del campo |
| Modal | **Arreglado:** regla genérica + respaldo de coordenadas |
| Guardar sin cerrar | **Arreglado** (supervisor + instrucciones) |
| Teclas bloqueadas (`Ctrl+L`, `F12`, `Esc`) | Sin cambio; no se ha probado en una app distinta |
| Colores de acento claros (amarillo) o un tema oscuro | **No cubierto:** el detector exige fondo oscuro con color |
| Conteo de filas por la IA | **Abierto** (ver arriba) |

### 6) Opción A para E3: copiar el identificador de cada fila (decidido por ti; solo local)
- **Reglas de la prueba:** mientras corría la evaluación del set oculto, **no se tocó el servidor** (sin
  deploy, `git pull`, reinicios ni `bench.py --base`). Todo en local y contra mi escritorio de práctica.
  - *Escritorio:* `bench.py` usa el de mi `.env` (tarjeta de `/evento`); el BRIEF dice que el evaluador
    recibe "un escritorio distinto del tuyo". No se pudo verificar la URL del evaluador desde aquí.
  - *Llave de OpenRouter compartida:* antes de gastar se consultó el saldo (solo lectura): US$41.21
    restantes de un límite de US$45; la prueba costó ~US$0.75 (≈ 2 %).
- **Qué falló antes:** la IA contaba "19 filas" en páginas de 20 (E3: 43 en vez de 45, dos veces con el
  mismo número). La lectura no perdía filas (medido en el punto anterior).
- **Qué se cambió (`llm.py`):** en cada página la IA copia en su nota el identificador de **cada** fila
  (código o primera columna), una por una, las cuenta y comprueba que coincida con las filas que ve
  (las páginas completas suelen tener todas el mismo número; la última menos); anota solo la página actual.
  El tope de una nota sube de 400 a 800 caracteres para que quepan ~20 códigos.
- **Regla de aceptación acordada:** E3 con al menos 2 de 3 y que ningún otro caso falle; si no, revertir.
- **Medido:**
  - **E3 ×3: 3 de 3** (97 s, 109 s, 97 s; US$0.047–0.063; 11 pasos; respuesta 45 las tres veces).
  - **Los 5 casos: 5 de 5**, y E3 acertó otra vez (4 de 4 en total con la opción A).
  - En las notas se ve por qué: 20 + 20 + 11 códigos copiados, 16 + 18 + 11 exactas, 6 descartadas de
    "e Hijos" → 45.
- **Antes → después (E3, mismo tema nuevo):** 1 de 3 (43, 43 y un acierto) → 4 de 4.
- **Costo/tiempo:** E3 sigue en ~100 s y ~US$0.05–0.06 (sin cambio apreciable). En esta corrida E1 tardó
  127 s y 16 pasos; es la variación habitual (la corrida 12 dio 118 s y 14 pasos).
- **Límites honestos:** son 4 muestras de E3; el acierto depende de que la IA copie bien los códigos. En
  una medición la IA empezó leyendo la página sin filtrar por estado y se corrigió sola. Está
  **commiteado en local y sin subir a GitHub ni publicar en el servidor**, a la espera de tu orden.

### 7) Regla general anti-ciclo (el ciclo de la clínica) — solo local, sin publicar
- **Qué falló (en la evaluación del set oculto, app de la clínica):** el agente abría la cita C-1460, la
  cerraba, filtraba y la volvía a abrir, una y otra vez, hasta el tope de 270 s.
- **Por qué la regla que existía no lo veía:** solo detectaba *la misma acción tres veces seguidas sobre la
  misma pantalla*. Este ciclo alterna tres acciones distintas y las pantallas cambian entre una y otra.
- **Qué se cambió (`supervisor.py`, `llm.py`, `agent.py`):**
  1. Cada acción se describe por *lo que hace en la app* (el texto del botón o enlace, el texto escrito y
     su campo), no por números de la lista ni por posiciones.
  2. Antes de ejecutar una acción se mira si, junto con las anteriores (de 2 a 6 acciones), completa una
     **secuencia que ya se hizo antes empezando en la misma pantalla** (los textos de la pantalla se parecen
     ≥ 85 %). Hace falta que haya al menos un clic y que no sea la misma acción repetida.
  3. Si es un ciclo, se rechaza: la IA recibe un aviso con la secuencia, y esa secuencia queda en una lista
     **"SECUENCIAS PROHIBIDAS"** que se le muestra en cada paso siguiente. Se le pide probar otro botón o
     enlace, desplazarse, otro menú o leer el registro completo antes de cerrarlo; y, si ya probó todo,
     reportar `fallida` explicando qué intentó.
  4. Instrucciones nuevas ("NO DES VUELTAS"): leer un registro completo antes de cerrarlo y no reabrirlo
     para buscar lo mismo.
- **Qué NO se bloquea (probado):** dos registros distintos con los mismos botones (Aplicar/Cerrar), paginar
  con "Siguiente", volver a la página anterior para recontar y seguir, reintentar el mismo clic porque la
  pantalla no cambió (el modal que ignora el primer clic) y llenar un formulario con Tab y texto.
- **Medido:**
  - 10 pruebas nuevas, incluida una con el agente completo y un escritorio de mentira que reproduce la
    secuencia abrir → Cerrar → Filtrar → abrir → **Cerrar (rechazado)** → scroll. Se comprobó que las
    pruebas **fallan si la regla se apaga**. En total pasan 82.
  - **Regresión en el escritorio de práctica: 0 rechazos por ciclo en 9 corridas reales** (5 casos + 4
    repeticiones), es decir, ningún falso positivo.
- **Qué NO se pudo medir:** no hay una copia de la app de la clínica en local, así que el ciclo real **no se
  probó contra ella**; se reprodujo su secuencia exacta de forma simulada. Cuánto tiempo ahorra es una
  **estimación**: la regla actúa tras unas 4–5 acciones (≈ 40–50 s a 8–10 s por paso) en lugar de 270 s.
- **Límites conocidos:** (a) un ciclo con una pantalla que cambia mucho en cada vuelta (por ejemplo una
  lista que se reordena) no se reconoce como "la misma pantalla"; (b) ciclos de más de 6 acciones no se
  detectan; (c) la regla impide repetir, pero no garantiza que la IA encuentre el dato: puede terminar
  `fallida`.
- **Dos fallos de la corrida de 5 casos que NO vienen de esta regla (0 ciclos prohibidos):**
  - **E4, `ConnectionClosedError`:** la conexión VNC se cortó a mitad de la tarea y no hay reconexión después
    de conectar (solo un reintento al inicio). Repetido: pasó (104 s).
  - **E3, respondió 16 con "única página":** contó una sola página aunque "Siguiente" estaba en la lista y
    aprovechó la frase de escape de la regla de conteos. Repetido 3 veces: 45, 45, 45.
  - *Abierto, a tu decisión:* (1) pedir que antes de afirmar "única página" se **pruebe** pulsar "Siguiente"
    y se compruebe que no cambia la pantalla; (2) reconectar el VNC una vez si se corta durante la tarea.

---

## Riesgos y pendientes conocidos
- `ReadTimeout` contra el publicado: sin causa establecida (cambio 13).
- La IA es lo más lento (5 s por llamada o más). Secuencias de varias acciones por decisión quedan **para después del imprevisto**.
- E3 acierta 2 de 3 veces: la IA a veces se salta una fila al contar una página de 20 (cambio 18).
- **E3 (conteo de filas):** con la opción A acertó 4 de 4 (antes ~la mitad). Pocas muestras; si en la evaluación falla, el síntoma sería un conteo off-by-uno.
- **Frase de escape "única página":** la IA puede afirmarlo sin comprobarlo (1 caso en 8 corridas de E3).
- **Conexión VNC cortada a mitad de tarea:** hoy la tarea termina `fallida` (1 caso).
- **Tema nuevo en servidor:** lo publicado está detrás del repo; falta `git pull && ./deploy.sh`.
- Lo publicado en el servidor está **detrás** del repo: falta `git pull && ./deploy.sh` cuando decidas publicar.
- El efecto de `Ctrl+A` en listas y de los hilos aparte no se aisló con medición.
