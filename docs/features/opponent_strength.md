# Feature: fuerza de calendario por rival

Implementación: `mlb_kaizen.training.build_dataset.build_point_in_time_rows_with_opponent_strength`  
Versión de fórmula: `opponent_strength_formula_v1`

## Qué mide

Para cada equipo que juega un partido se generan cuatro índices: ofensiva y
prevención promedio de los rivales que ese equipo ya enfrentó; se calculan
para local y visitante. Cada rival pesa por el número de enfrentamientos
previos contra el equipo.

Un valor de 1.0 representa un rival promedio de liga. Un valor mayor de 1.0
en ofensiva indica que el club enfrentó ofensivas que anotaban más que el
promedio; en prevención, que enfrentó defensas que permitían más carreras que
el promedio. Son descriptores del calendario anterior, no una calificación
absoluta del equipo.

## Disponibilidad temporal

La entrada procede exclusivamente de resultados finalizados antes del inicio
del partido de la fila. Para una fila en el instante `T`:

1. se toman únicamente rivales enfrentados antes de `T`;
2. el perfil de cada rival usa únicamente sus partidos acumulados antes de
   `T`;
3. el resultado de la partida que se está prediciendo se añade **después** de
   calcular sus features.

Esto permite un backtest point-in-time con resultados históricos. Reutiliza el
contrato temporal del dataset de equipo; no afirma que una API hubiese dado un
snapshot separado en tiempo real.

## Fórmula

Para un equipo `t`, con conjunto de rivales anteriores `O(t)`, número de
encuentros `n(t,o)` y promedio de carrera de liga anterior `L`:

```text
opponent_offensive_index(t) =
  sum(n(t,o) * (runs_scored(o) / games(o)) / L) / sum(n(t,o))

opponent_run_prevention_index(t) =
  sum(n(t,o) * (runs_allowed(o) / games(o)) / L) / sum(n(t,o))
```

## Umbrales y datos faltantes

- Al menos un partido anterior por equipo.
- Al menos diez apariciones de equipo acumuladas para calcular el promedio de
  liga.
- Al menos un rival enfrentado antes por cada equipo.
- Si no se cumple un umbral, el partido alimenta los acumuladores posteriores
  pero no genera fila de entrenamiento. No se inventa un rival “promedio”.

## Límites

La señal no corrige todavía el índice principal de ofensiva/prevención; se
entrega como entrada independiente al modelo para que la evaluación temporal
determine si añade valor. No debe interpretarse como fuerza completa de un
equipo: no incluye lesiones, lineups, viajes ni calidad individual de pitcher.

Cambiar la ponderación, añadir ventanas móviles o sustituir los índices exige
una versión nueva de fórmula, nuevos tests y un experimento separado.
