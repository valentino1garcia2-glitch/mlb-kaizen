# Feature: rendimiento separado en casa y visita

Implementación experimental: `mlb_kaizen.training.build_dataset.build_point_in_time_rows_with_opponent_strength_recent_form_and_site_splits`  
Versión de fórmula: `site_split_formula_v1`

## Fórmula y temporalidad

Para un partido, el local usa sólo sus juegos previos como local y el visitante
sólo sus juegos previos como visitante. Se calculan índices de carreras
anotadas y permitidas contra el promedio de liga disponible antes del partido.
Los acumuladores se reinician por temporada y se actualizan después de crear
la fila, por lo que no incluyen resultado propio ni futuro.

## Estado experimental

E10 mejoró mínimamente 2025 pero no repitió esa mejora en el test 2026.
Permanece documentada para trazabilidad, pero **no se conserva como señal
activa**.
