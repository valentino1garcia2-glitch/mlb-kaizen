# E8 — Forma reciente point-in-time

## Pregunta

¿La forma ofensiva y defensiva de los últimos juegos de cada equipo aporta
información que el promedio acumulado y la fuerza previa de rivales no captan?

## Hipótesis

Un equipo puede cambiar durante una temporada por rendimiento, lesiones o
racha. Sus últimos partidos pueden describir mejor su estado actual que todo
el historial acumulado, sin necesitar lineups históricos postpartido.

## Diseño fijado antes de evaluar

- Fuente: la misma colección normalizada local auditada de MLB, 2022–2026.
- Ventana: últimos **15** partidos terminados de cada equipo.
- La ventana se reinicia para cada equipo al comenzar una nueva temporada; no
  se arrastra la forma de octubre al siguiente año.
- Nuevas entradas: ofensiva y prevención reciente para local y visitante,
  normalizadas contra el promedio de liga disponible antes del partido.
- Control: Poisson E3 + E7, sobre exactamente las mismas filas E8.
- Candidato: el mismo modelo, más las cuatro entradas de forma reciente.
- Selección: entrenar 2022–2024 y evaluar 2025.
- Test final: entrenar 2022–2025 y evaluar 2026 solo si el candidato mejora
  Brier **y** log loss frente al control en 2025.
- La evaluación es determinista: no hay semilla aleatoria que seleccionar.
- Si 2025 no mejora ambas métricas, se documenta como negativo y no se usa
  2026 para rescatar la idea.

## Salvaguardas

Cada ventana se consulta antes de insertar el resultado del partido actual.
Las pruebas cubren exclusión del marcador propio, exclusión de un marcador
futuro, reinicio anual, validación del tamaño de ventana y timestamps.

## Resultado

### FACT

E8 generó 10,696 filas, pues cada temporada espera 15 partidos previos de
ambos clubes para medir forma reciente. La validación 2025 usa 6,470 filas de
entrenamiento (2022–2024) y 2,171 de evaluación. El test final 2026 usa 8,641
filas de entrenamiento (2022–2025) y 2,055 de evaluación.

| Corte | Modelo | Brier | Log loss | MAE local | MAE visitante |
| --- | --- | ---: | ---: | ---: | ---: |
| Validación 2025 | Control E3+E7, mismas filas | 0.245308 | 0.683621 | 2.396998 | 2.622371 |
| Validación 2025 | E8 + forma reciente | **0.244775** | **0.682519** | **2.392903** | **2.616148** |
| Test 2026 | Control E3+E7, mismas filas | 0.245277 | 0.683573 | 2.448243 | 2.537567 |
| Test 2026 | E8 + forma reciente | **0.245110** | **0.683250** | **2.443752** | 2.538097 |

La mejora de ambas métricas en 2025 habilitó una única medición de 2026. Allí
también bajan Brier (0.000167) y log loss (0.000323) sobre el control idéntico.

### INTERPRETACIÓN

E8 aporta una mejora pequeña y reproducida temporalmente sobre E3+E7. Se
conserva como señal experimental candidata. El menor número de filas no es una
mejora por sí mismo: se controla evaluando E3+E7 en exactamente la misma
cohorte E8. No existe aún validación de producción ni evidencia de
rentabilidad.

### HIPÓTESIS SIGUIENTE

Los días de descanso entre juegos pueden afectar rendimiento y no requieren
datos externos: se derivan de fechas de partidos anteriores. Deben probarse
como un experimento separado y pre-registrado contra E3+E7+E8.
