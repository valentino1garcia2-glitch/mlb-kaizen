# E6-A — Auditoría temporal de lineups históricos — 2026-10-03

## Pregunta y alcance

¿Existe evidencia que demuestre que una alineación histórica se conocía antes
del inicio de cada juego? Esta auditoría no crea features, no entrena modelos y
no altera E0--E5.

## Fuentes inspeccionadas

| Fuente | Datos disponibles | Timestamp | Clasificación para E6 |
| --- | --- | --- | --- |
| Colección normalizada 2022--2026 | game id, equipos, hora de juego, resultados, pitchers probables y estadio; no jugadores ni orden de bateo | No `retrieved_at`, `known_at` ni `published_at` por juego | **POSTGAME_ONLY** para el histórico de resultados; no contiene lineup. |
| Colección plana v2 (12,045 juegos) | game id, equipos, hora, resultado, pitcher probable y `retrieved_at`; no lineup | `retrieved_at` es B: momento de descarga. Los 12,045 registros fueron descargados al inicio o después del juego; 0 antes | **POSTGAME_ONLY**. |
| Archivos crudos de schedule 2022--2026 | schedule final, marcador y `linescore`; no lista de nueve bateadores ni mapa de jugadores por equipo | Sin timestamp de descarga/publicación en el payload | **POSTGAME_ONLY**. |
| API MLB Stats `/game/{id}/boxscore` en el proveedor | puede devolver `game_id`, equipo, `player_id`, orden de bateo, posición y estado `CONFIRMED` | Sólo `retrieved_at` local (B); no expone `published_at`/`known_at` oficial (A) | **USABLE_WITH_LIMITATIONS** sólo para snapshots prospectivos antes del inicio. |
| Base SQLite local | 15 snapshots de juego; no tabla `lineup_snapshots` aplicada y cero snapshots de lineup | No hay timestamps de lineup históricos | **UNKNOWN_TIMESTAMP** para el histórico actual. El diseño de migración sí permite capturar B prospectivamente. |
| Caché local | un snapshot de schedule pregame con `retrieved_at` B | No contiene lineup | **UNKNOWN_TIMESTAMP** para E6: prueba horario del schedule, no de lineup. |

## Cobertura observada

| Temporada | Juegos normalizados | Juegos con lineup | Timestamp usable de lineup | Confirmados pregame |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 2,430 | 0 | 0 | 0 |
| 2023 | 2,430 | 0 | 0 | 0 |
| 2024 | 2,430 | 0 | 0 | 0 |
| 2025 | 2,430 | 0 | 0 | 0 |
| 2026 | 2,325 | 0 | 0 | 0 |
| **Total** | **12,045** | **0 (0%)** | **0 (0%)** | **0 (0%)** |

La distribución de minutos antes del juego no existe: no hay ninguna
observación histórica con lineup y hora usable.

## Evidencia sobre leakage

**FACT.** Los 37 archivos raw contienen juegos mayoritariamente o totalmente
`Final`; sus `linescore.offense/defense.battingOrder` son números de orden del
bateador/defensa presente dentro del juego, no la lista inicial de nueve ni una
marca de publicación. Los conteos de `battingOrder` de linescore (2,314--2,437
por temporada) no son lineups y pueden reflejar sustituciones posteriores.

**FACT.** Ninguno de los 12,045 registros v2 se descargó antes de su hora de
inicio; además, ninguno tiene campos de lineup. Usar sus resultados, líneas de
boxscore, rosters retrospectivos o el boxscore consultado hoy para un juego
pasado filtraría información postpartido.

**INTERPRETATION.** El parser de `boxscore` es adecuado para operación futura:
si guarda un snapshot `CONFIRMED` con `retrieved_at < game_start_time`, prueba
que el sistema conocía esa alineación antes del juego. Sin embargo, no puede
reconstruir esa condición para temporadas pasadas, y una respuesta consultada
después del juego no se vuelve pregame porque contenga `battingOrder`.

## Campos requeridos y estado actual

| Campo | Histórico actual | API/snapshot prospectivo |
| --- | --- | --- |
| `game_id`, equipo | Sí | Sí |
| `player_id`, orden de bateo | No | Sí, al publicar MLB el lineup |
| estado de lineup | No | Sí (`CONFIRMED`/ausencia) |
| inicio del juego | Sí | Se obtiene del schedule y se debe unir |
| hora de publicación A | No | No |
| hora observada B | No para lineups | Sí (`retrieved_at`) |

## Decisión

**E6_DATA_BLOCKED.** La cobertura histórica pregame verificable es 0/12,045;
por tanto no se puede construir ni evaluar E6-B sin leakage.

**HYPOTHESIS.** E6 podría reabrirse al obtener un archivo histórico versionado
con `game_id`, ambos lineups iniciales, estado, y `known_at` o `retrieved_at`
anterior al inicio, o al comenzar a capturar snapshots prospectivos por las
ventanas definidas en `docs/snapshot-policy.md`. Antes de E6-B se debe auditar
esa nueva fuente, medir su cobertura y excluir cualquier snapshot posterior al
inicio.
