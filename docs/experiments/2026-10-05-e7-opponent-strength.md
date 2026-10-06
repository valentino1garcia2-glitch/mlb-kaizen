# E7 — Calidad previa de rivales

## Pregunta

¿El rendimiento de los equipos gana información útil al añadir la calidad de
los rivales que cada uno ya enfrentó, sin usar datos del partido que se va a
predecir ni de partidos futuros?

## Hipótesis

Los índices actuales de ofensiva y prevención pueden estar distorsionados por
un calendario fácil o difícil. La calidad acumulada de los rivales anteriores
podría explicar esa diferencia y mejorar la predicción de victoria local.

## Datos y construcción

- Fuente: colección normalizada local auditada de MLB, temporadas 2022–2026.
- Constructor: `build_point_in_time_rows_with_opponent_strength`.
- Nuevas entradas: promedio ponderado por enfrentamientos de los índices
  previos de ofensiva y prevención de los rivales de local y visitante.
- Un rival solo cuenta después de un enfrentamiento terminado anterior.
- Sus estadísticas se leen antes de actualizar los acumuladores del partido
  actual. Por tanto, ni el marcador propio ni uno futuro puede entrar en su
  fila.
- Umbrales fijados antes de evaluar: al menos 1 juego previo por equipo, 10
  apariciones de equipo en el promedio de liga y 1 rival previo por equipo.

## Comparación y protocolo

- Control: Poisson E3 (`alpha=0.0001`) con las cinco entradas de equipo ya
  existentes.
- Candidato: el mismo Poisson E3, más las cuatro entradas de calidad de
  rivales.
- Se comparan sobre exactamente las mismas filas generadas por E7.
- Selección: entrenar 2022–2024 y evaluar 2025.
- Prueba final: entrenar 2022–2025 y evaluar 2026, solo si el candidato mejora
  **Brier y log loss** sobre el control en 2025.
- Métricas: Brier y log loss. La evaluación es determinista; no hay semilla
  aleatoria que elegir.
- Criterio de parada: si no mejora ambas métricas en 2025, E7 se documenta como
  experimento negativo y 2026 no se usa para ajustar o rescatar la idea.

## Salvaguardas

Las pruebas de este bloque cubren: exclusión del resultado propio, exclusión
de un resultado futuro, umbrales inválidos y timestamps de feature no
posteriores a la predicción.

## Resultado

### FACT

El constructor produjo 11,836 filas. La validación 2025 usa 7,153 filas para
entrenar (2022–2024) y 2,400 para medir (2025). El test 2026 usa 9,553 para
entrenar (2022–2025) y 2,283 para medir (2026).

| Corte | Modelo | Brier | Log loss | MAE local | MAE visitante |
| --- | --- | ---: | ---: | ---: | ---: |
| Validación 2025 | Control E3, mismas filas | 0.245522 | 0.684097 | 2.404947 | 2.610433 |
| Validación 2025 | E7 + fuerza de rivales | **0.245235** | **0.683492** | **2.401983** | **2.606278** |
| Test 2026 | Control E3, mismas filas | 0.245949 | 0.684965 | 2.464117 | 2.541378 |
| Test 2026 | E7 + fuerza de rivales | **0.245633** | **0.684313** | **2.463020** | **2.538447** |

La mejora en ambas métricas de 2025 cumplió el criterio fijado antes del test,
por lo que se abrió una sola vez 2026. Allí se repite: Brier mejora 0.000316 y
log loss 0.000652 respecto al control de las mismas filas.

### INTERPRETACIÓN

E7 es la primera feature nueva, después de E3, que mejora de forma consistente
la referencia E3 en validación temporal y test final. Se conserva como
**señal experimental candidata**, no como garantía de predicción ni de
rentabilidad: la magnitud es pequeña y sólo se ha probado un corte anual.

La cifra no se compara directamente con el Brier 0.2463 citado históricamente
para E3, porque aquel experimento utilizó un subconjunto de filas distinto.
El control incluido aquí elimina justamente ese sesgo de comparación.

### HIPÓTESIS SIGUIENTE

Una ventana de forma reciente puede complementar este ajuste de calendario.
Debe evaluarse como un experimento nuevo, sin modificar E7 ni elegir sus
parámetros mirando 2026.
