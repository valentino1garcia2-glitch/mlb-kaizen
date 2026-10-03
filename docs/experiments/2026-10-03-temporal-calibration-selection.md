# Selección temporal de calibración — 2026-10-03

## Pregunta

¿Qué corrección de probabilidad mejora el modelo E3 sin escoger un método con
la temporada 2026 a la vista?

## Protocolo

Se definieron antes dos métodos: rangos con suavizado y Platt. Cada modelo de
carreras se entrenó sólo con años anteriores. Las predicciones de 2024
ajustaron cada calibrador; 2025 eligió el método; el método elegido se ajustó
con 2025 y se midió una sola vez en 2026.

## Resultado

| Etapa | Rangos | Platt |
| --- | ---: | ---: |
| Selección 2025 — Brier | 0.2458 | **0.2447** |
| Selección 2025 — log loss | 0.6847 | **0.6824** |

Platt fue elegido sin observar 2026. Al ajustar con las observaciones de 2025
y aplicar a 2026: Brier **0.2463 → 0.2462** y log loss **0.6856 → 0.6855**.

## Decisión

`PlattCalibrator` queda disponible como calibrador temporal reutilizable y
serializable. La mejora es modesta y no autoriza la etiqueta de producción.
No se conecta aún a Analyst Mode hasta que éste cargue el mismo modelo
entrenado E3 al que corresponde la calibración.
