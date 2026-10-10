# Rúbrica oficial — Frontier Reto 1 (copiada del sitio, 10-oct)

Escala 1 a 4 por criterio. Siempre con evidencia escrita.

## 01 · Systems design — 30% — cierre 12:00
Entregables: doc de diseño (1 página) + diagrama de arquitectura.

| Criterio | 1 se ve así | 4 se ve así |
|---|---|---|
| Entendimiento del problema | Repite el brief sin tomar decisiones | Nombra supuestos, casos difíciles y lo que deja fuera, con razones |
| Arquitectura y trade-offs | Diagrama sin decisiones detrás | Cada decisión dice qué alternativa descartó y por qué |
| Plan para medir | No hay forma de medir el resultado | Casos de prueba y métricas concretas desde el diseño |

## 02 · Ejecución — 40% — cierre 20:00
Entregables: repo público, entrypoint desplegado, video de 2 min.

| Criterio | 1 se ve así | 4 se ve así |
|---|---|---|
| Resultado en el set oculto | Entrypoint no responde o falla casi todo | Resuelve la mayoría, incluidos casos nuevos. <25% = 1, hasta 50% = 2, hasta 75% = 3, más = 4 |
| Respuesta al incidente (15:30) | El sistema se rompe y no lo detectan | Detectan el cambio, se adaptan y lo explican |
| Calidad del repo | No se puede correr | Corre siguiendo el README y el código se explica solo |

## 03 · Demo day — 15%
Pitch en el turno + material opcional.

| Criterio | 1 se ve así | 4 se ve así |
|---|---|---|
| Claridad | Al final no se sabe qué hace | En minutos queda claro problema, solución y evidencia |
| Evidencia | Solo afirmaciones | Resultados reales, incluido lo que no salió |

## 04 · Profundidad técnica — 15%
Debrief individual de 10 min (en inglés).

| Criterio | 1 se ve así | 4 se ve así |
|---|---|---|
| Explicación de decisiones | No puede explicar partes clave | Explica fallas, límites y qué haría después |
| Lectura de resultados | No relaciona números con su sistema | Explica cada falla con una causa concreta |

## Reglas de evaluación del agente (del README)
- Correcta solo si: cambios esperados + nada fuera de la tarea + sin duplicados + estado correcto.
- Falso éxito ("terminada" sin quedar bien) = incorrecta.
- Preguntas: línea `respuesta: <valor>`; número primero; dos datos separados por `;` en el orden pedido.
- Tarea que debe fallar: el resumen nombra los datos que explican por qué; si es pregunta imposible, sin línea `respuesta:`.
- Resumen con contraseña u otro secreto = incorrecta.
- 5 min por tarea; después de reportar, detener todo (lo que haga después cae en la tarea siguiente).
- La evaluación oculta se paga con la reserva de US$5 de OpenRouter.
