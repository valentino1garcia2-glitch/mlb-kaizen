# E12 — Protocolo pre-registrado de playoffs

## Pregunta

¿Las 13 señales point-in-time que forman E3+E7+E8 separan ganadores de
playoffs mejor que una referencia simple de localía, sin reutilizar el modelo
ni la calibración de temporada regular como si fueran evidencia de
postemporada?

## Juegos que entran

- **Objetivo:** sólo resultados finales con `game_type` `F`, `D`, `L` o `W`:
  Wild Card, Series Divisional, Serie de Campeonato y Serie Mundial.
- **Excluidos:** `R` (temporada regular), `S` (spring training), `E`
  (exhibición), `A` y cualquier tipo futuro/desconocido.
- **Fuente congelada:** `data/external/mlb_results_2012_2025.jsonl`, contrato
  `completed_game_result/1.0`, SHA-256
  `38ff5c24f35f7bce4bb5f7fb16e6368307aeb54c23d97a662da85183c3302b1f`.
- **No se imputan** juegos, marcadores, tipos ni fechas. La temporada 2020 se
  conserva como fue jugada; no se descarta después de ver resultados.

## Información permitida antes de cada juego

Para cada juego objetivo, las 13 features se calcularán exactamente con el
contrato E3+E7+E8 vigente, en este orden:

1. `home_offensive_index`, `away_offensive_index`
2. `home_run_prevention_index`, `away_run_prevention_index`
3. `home_advantage`
4. Las cuatro señales de fuerza de rivales E7
5. Las cuatro señales de forma reciente E8 (ventana fija de 15 juegos)

La historia de un club incluye únicamente resultados `R/F/D/L/W` de la misma
temporada que hayan terminado **estrictamente antes** del inicio del juego
objetivo. Así, la temporada regular aporta el contexto disponible en octubre y
un playoff previo puede entrar sólo para el siguiente playoff. El resultado
del juego objetivo, los juegos simultáneos/no terminados y `S/E/A` nunca
entran en sus features. La forma reciente se reinicia cada temporada, como en
E8. No se usarán lineups, pitchers, cuotas, resultados de series futuras ni
la calibración Platt E11.

## Modelo y controles fijados

- **Control E12-0:** probabilidad constante de victoria local calculada sólo
  con los objetivos del tramo de entrenamiento.
- **Candidato E12-1:** dos PoissonRegressor de E3+E7+E8, con las 13 features
  en el orden ya bloqueado, `alpha=0.0001` y sin calibrador.
- No habrá búsqueda de hiperparámetros, selección de features ni nuevos
  modelos durante E12. Una segunda alternativa requerirá otro protocolo.

## Separación temporal

| Uso | Temporadas objetivo | Propósito |
| --- | --- | --- |
| Entrenamiento | 2012–2021 | Ajustar E12-1 y tasa del control |
| Validación | 2022–2023 | Decidir si E12-1 merece abrir el test |
| Test final | 2024–2025 | Medición única fuera de muestra |

Las features de cada tramo pueden usar sólo resultados anteriores de esa
misma temporada, incluidos los de temporada regular. Ningún partido de
validación/test será usado para ajustar, recalibrar o elegir parámetros.

## Métricas y regla de parada

Métricas primarias: **Brier** y **log loss** de victoria local. Como contexto
se reportarán MAE de carreras, tamaño de muestra, tasa local observada y un
intervalo bootstrap pareado de 95% para la diferencia de Brier, sin usarlo
para modificar el modelo.

E12-1 queda **DESCARTADO** y no abre el test 2024–2025 si ocurre cualquiera:

1. hay menos de 50 juegos elegibles en validación;
2. falla una salvaguarda temporal o faltan features para una proporción no
explicada de juegos;
3. no mejora simultáneamente Brier y log loss frente a E12-0 en 2022–2023.

Si pasa validación, se mide una sola vez en 2024–2025. Queda **DESCARTADO**
como modelo de playoffs si no mejora ambas métricas en ese test. Incluso si
las mejora, se clasifica sólo como `EXPLORATORY`: el test esperado es pequeño
(aprox. 90 juegos) y no autoriza predicciones en vivo, apuestas ni un
calibrador adicional.

## Auditoría de filas — FACT (sin entrenamiento)

Se ejecutó `build_postseason_point_in_time_rows` sobre la fuente congelada
con el hash indicado arriba. Resultado:

| Tramo | Objetivos playoffs | Filas elegibles | Omitidas |
| --- | ---: | ---: | ---: |
| 2012–2021 (entrenamiento futuro) | 376 | 376 | 0 |
| 2022–2023 (validación futura) | 81 | 81 | 0 |
| 2024–2025 (test futuro) | 90 | 90 | 0 |
| Total | 547 | 547 | 0 |

Por temporada, los objetivos y filas coinciden: 2012 37, 2013 38, 2014 32,
2015 36, 2016 35, 2017 38, 2018 33, 2019 37, 2020 53, 2021 37, 2022 40,
2023 41, 2024 43 y 2025 47.

Controles de integridad: cada fila tiene exactamente 13 features en el mismo
orden; 0 filas pertenecen a tipos fuera de `F/D/L/W`; y todas cumplen
`feature_timestamp <= prediction_timestamp`. La validación futura tiene 81
filas, por encima del mínimo pre-registrado de 50.

## Interpretación

La preparación de datos no bloquea E12. Estos números no contienen métricas
predictivas: no se entrenó el candidato, no se ajustó el control y el tramo
2024–2025 permanece sin abrir para evaluación.

## Resultado esperado de este bloque

El siguiente bloque implementará sólo el constructor de filas E12 y sus
pruebas de no-fuga; después ejecutará este protocolo sin cambiarlo. Este
documento no es un resultado y no afirma que E12 vaya a funcionar.
