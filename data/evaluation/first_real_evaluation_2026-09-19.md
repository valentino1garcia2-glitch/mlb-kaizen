# Primera evaluación real — walk-forward sobre 11,836 partidos (2022-2026)

Fecha: 2026-09-19
Dataset: `data/historical/2022_2026_point_in_time.jsonl` (derivado de
`data/external/mlb_kaizen_colab_2026-09-19/`, auditado en HANDOFF.md sección 21)
Split evaluado: filas 8000-11836 (fold único, mismo split para ambos modelos
y para la referencia ingenua, comparación justa)

## Resultados

| Modelo | home MAE | away MAE | total RMSE | Brier | Log loss |
|---|---|---|---|---|---|
| Referencia ingenua (probabilidad constante = tasa de victoria local del fold de entrenamiento) | — | — | — | 0.2490 | 0.6912 |
| Baseline Poisson (`PoissonTrainer`) | 2.4662 | 2.5932 | 4.5402 | 0.2494 | 0.6919 |
| Random Forest challenger (`RandomForestTrainer`) | 2.4952 | 2.6403 | 4.6120 | 0.2542 | 0.7026 |

## Interpretación honesta

**Ninguno de los dos modelos supera de forma clara a una referencia ingenua**
que simplemente predice, para todo partido, la tasa histórica de victoria
del equipo local (52.95% en el fold de entrenamiento). El Brier score del
baseline Poisson (0.2494) es prácticamente idéntico al de la referencia
ingenua (0.2490); el Random Forest queda ligeramente peor que ambos en
todas las métricas.

Esto **no invalida el pipeline** — demuestra que funciona de punta a punta
con datos reales, sin fuga temporal, con walk-forward genuino. Lo que
demuestra es que, con las features actuales (`offensive_index` y
`run_prevention_index` calculados solo a partir de carreras
anotadas/permitidas acumuladas point-in-time, sin pitchers, sin bullpen,
sin lineup, sin clima, sin ajuste por rival), el modelo todavía no aporta
una ventaja predictiva medible sobre la tasa base de victoria local.

Regla del proyecto (sección 56 del prompt maestro y HANDOFF.md): no afirmar
ventaja real hasta contar con evidencia suficiente. Esta evaluación es
exactamente esa evidencia, y dice que **todavía no la hay** con las features
actuales.

## Nota sobre el error absoluto de carreras (MAE ~2.5)

El promedio real de carreras por equipo en el dataset es 4.45-4.47. Un MAE
de ~2.5 carreras es un error relativo grande (más del 50% de la media), pero
hay que contextualizarlo: el proceso de anotación de carreras en béisbol
tiene varianza alta de por sí incluso con información perfecta (un
Poisson/Binomial Negativa con media ~4.4 y dispersión moderada ya tiene una
desviación estándar de varias carreras). No se puede concluir de esta única
cifra si el error es "malo" sin comparar contra el error irreducible teórico
del proceso — pendiente de análisis más fino.

## Qué falta para que esto cambie

Por orden de impacto probable, no por facilidad de implementación:

1. Ajustar por fuerza del pitcher abridor (el propio dataset ya trae
   `probable_pitchers` — no usados todavía en las features).
2. Ajustar por parque (factor de parque, no solo home_advantage genérico).
3. Ventana móvil de forma reciente en vez de acumulado de temporada completa
   (un equipo de abril no es el mismo que en septiembre).
4. Ajuste por fuerza del rival (SOS).
5. Recalibración de probabilidad (Platt scaling / isotonic) en vez de la
   PMF Binomial Negativa cruda.

Ninguno de estos se implementó todavía — este documento es el punto de
partida real para decidir cuál priorizar, con evidencia, no con intuición.

## Reproducibilidad

```bash
python3 -c "
from pathlib import Path
from mlb_kaizen.training.dataset import load_jsonl
from mlb_kaizen.training.trainers import PoissonTrainer, RandomForestTrainer
from mlb_kaizen.evaluation.walk_forward import walk_forward_evaluate

rows = load_jsonl(Path('data/historical/2022_2026_point_in_time.jsonl'))
summary = walk_forward_evaluate(rows, lambda: PoissonTrainer(), 'poisson_v1',
                                 min_train_size=8000, test_window=3836)
print(summary)
"
```
