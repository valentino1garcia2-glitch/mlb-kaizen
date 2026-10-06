# Feature: días de descanso

Implementación experimental: `mlb_kaizen.training.build_dataset.build_point_in_time_rows_with_opponent_strength_recent_form_and_rest_days`  
Versión de fórmula: `rest_days_formula_v1`

## Fórmula y temporalidad

Para cada equipo, el descanso es el número de días completos sin jugar entre
la fecha del último partido anterior y la fecha del partido actual:

```text
rest_days = max(0, current_game_date - prior_game_date - 1)
```

Un partido al día siguiente o una doble cartelera da 0. El último partido se
registra sólo después de crear la fila actual, por lo que este dato nunca usa
el marcador propio ni uno futuro.

## Estado experimental

E9 lo evaluó como feature independiente sobre E3+E7+E8. No mejoró Brier ni
log loss en la validación 2025, por lo que no se midió 2026. La fórmula queda
documentada para trazabilidad y posible rediseño futuro, pero **no se conserva
como señal activa**.
