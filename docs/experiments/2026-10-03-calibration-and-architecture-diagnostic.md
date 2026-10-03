# Diagnóstico de calibración y arquitectura — 2026-10-03

## Pregunta

¿La falta de mejora incremental de abridor, parque y bullpen indica ausencia
de señal, o que el modelo y la aplicación no pueden aprovecharla bien?

## Datos y protección temporal

- Dataset E3: `2022_2026_point_in_time_with_starters_min5.jsonl`.
- Para calibración: entrenar con 2022–2024, obtener predicciones de 2025,
  ajustar sólo con 2025 y medir una sola vez en 2026.
- No se eligieron parámetros mirando resultados de 2026.

## Resultados

- Predicción media 2026: **50.43%**; victorias locales reales: **53.11%**.
- Accuracy del modelo: **55.09%**; elegir siempre local: **53.11%**. La
  precisión en confianza alta fue **57.99%**.
- Calibración temporal: Brier 0.2463 → **0.2462**; log loss 0.6856 →
  **0.6855**. Mejora pequeña, no validación de producción.
- Redundancia: bullpen/previsión de equipo ≈0.87–0.88; parque/previsión local
  ≈0.70; abridor/previsión ≈0.38.

## Hallazgo de arquitectura y decisión

`training.baseline.PoissonRunModel` es el modelo entrenado y evaluado;
Analyst Mode usa `models.baseline.BaselineRunModel`, una fórmula fija distinta.
Antes de E6 lineups se debe diseñar una ruta versionada para cargar un modelo
entrenado en Analyst Mode, conservando la fórmula fija como fallback claramente
etiquetado.
