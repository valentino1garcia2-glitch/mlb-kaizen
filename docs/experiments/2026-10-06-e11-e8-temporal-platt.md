# E11 — Calibración Platt temporal para E3+E7+E8

## Pregunta

¿Una corrección Platt ajustada sólo con probabilidades históricas anteriores
mejora la calidad de los porcentajes del modelo E3+E7+E8?

## Diseño fijado antes de ejecutar

- Modelo de carreras: Poisson E3 con fuerza de rivales E7 y forma reciente E8.
- No se añaden nuevas features ni se modifica el modelo de carreras.
- Ajuste inicial: predicciones fuera de muestra de 2024, producidas entrenando
  sólo con 2022–2023.
- Selección: aplicar ese calibrador a predicciones fuera de muestra de 2025,
  producidas entrenando sólo con 2022–2024.
- Test final: si Brier **y** log loss mejoran ambos en 2025, ajustar Platt con
  las predicciones fuera de muestra de 2025 y aplicarlo una sola vez a las
  predicciones 2026, entrenadas con 2022–2025.
- Control: probabilidades E3+E7+E8 sin calibrar sobre exactamente los mismos
  partidos de cada año.
- Criterio de parada: si 2025 no mejora ambas métricas, no abrir 2026.

## Salvaguarda temporal

El calibrador nunca observa los resultados del año que se usa para reclamar
rendimiento. Es una corrección de probabilidades, no una nueva señal de juego.

## Resultado

### FACT

El ajuste inicial usó 2,160 predicciones fuera de muestra de 2024. Su Platt
tuvo pendiente 3.37048381 e intercepto -1.56550793. Aplicado a 2,171
predicciones fuera de muestra de 2025:

| Corte | Brier sin calibrar | Brier Platt | Log loss sin calibrar | Log loss Platt |
| --- | ---: | ---: | ---: | ---: |
| Selección 2025 | 0.244775 | **0.244062** | 0.682519 | **0.681098** |

Cumplió el criterio, por lo que Platt se ajustó una vez con las 2,171
predicciones de 2025 (pendiente 3.17253263, intercepto -1.45152099) y se
aplicó a las 2,055 predicciones 2026:

| Corte | Brier sin calibrar | Brier Platt | Log loss sin calibrar | Log loss Platt |
| --- | ---: | ---: | ---: | ---: |
| Test 2026 | 0.245110 | **0.244968** | 0.683250 | **0.682992** |

### INTERPRETACIÓN Y DECISIÓN

**KEEP como calibración experimental de E3+E7+E8.** La mejora se repite, pero
es pequeña. Platt corrige cómo se expresan los porcentajes; no añade
información nueva de partidos ni demuestra rentabilidad. Para usarla en el
análisis diario se necesita crear y versionar un artefacto que corresponda
exactamente al modelo E3+E7+E8, no reutilizar un calibrador de otro feature set.
