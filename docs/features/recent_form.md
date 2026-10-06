# Feature: forma reciente de equipo

Implementación: `mlb_kaizen.training.build_dataset.build_point_in_time_rows_with_opponent_strength_and_recent_form`  
Versión de fórmula: `recent_form_formula_v1`

## Qué mide

Para local y visitante, la feature resume carreras anotadas y permitidas en
los últimos 15 partidos terminados de la misma temporada. Cada tasa se divide
por el promedio de carreras de liga que ya existía antes del partido a
predecir. Un índice de 1.0 equivale a promedio de liga.

## Disponibilidad temporal

Para una predicción en el instante `T`, la ventana contiene solamente partidos
con inicio anterior a `T`. El resultado de la partida actual se agrega a la
ventana después de crear su fila, por lo que no puede entrar en sus propios
inputs. La ventana de cada equipo se vacía cuando comienza una temporada nueva:
la forma del cierre del año anterior no se hace pasar por información reciente.

## Fórmula

Con `W = 15`, resultados anteriores de un equipo `G(t)` y promedio de liga
anterior `L`:

```text
recent_offensive_index(t) = average(runs_scored in G(t)) / L
recent_run_prevention_index(t) = average(runs_allowed in G(t)) / L
```

Una fila sólo existe cuando ambos equipos tienen los 15 partidos anteriores
requeridos, además de los requisitos heredados de historia de equipo y fuerza
de rivales. No se rellena una ventana incompleta con un valor inventado.

## Límites

Quince juegos es una elección pre-registrada para E8, no un número optimizado
viendo 2026. Cambiar tamaño, ponderar por recencia o arrastrar datos entre
temporadas requiere una versión nueva de fórmula, pruebas nuevas y otro
experimento temporal.
