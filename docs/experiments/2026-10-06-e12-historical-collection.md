# E12-B preparatorio — colección histórica oficial 2012–2025

## Pregunta

¿Podemos construir un archivo local, reproducible y auditable de resultados
finales oficiales que separe temporada regular de playoffs antes de diseñar el
experimento E12?

## Insumo y método fijados antes de ejecutarlo

- Fuente: endpoint público de calendario MLB Stats API, resultados con estado
  `Final` y marcador publicado.
- Intervalo solicitado: 2012-03-01 a 2025-12-31.
- Cliente: `MLBStatsProvider.completed_games_batched`, en tramos no solapados
  de hasta 180 días para evitar truncamientos de intervalos largos.
- Salida local: `data/external/mlb_results_2012_2025.jsonl`, contrato
  `completed_game_result/1.0`.
- Cada fila conserva `game_type`. Se esperan `R` y códigos de postemporada;
  los códigos desconocidos se conservarán y contarán, no se reinterpretarán.

## Salvaguardas de temporalidad

Los marcadores son resultados retrospectivos: su `retrieved_at` describe la
descarga actual y **no** se usará como prueba de disponibilidad pregame. Un
futuro constructor de E12 sólo podrá acumular resultados con inicio
estrictamente anterior al partido objetivo. Este bloque no entrena, calibra ni
emite predicciones.

## Controles y criterio de parada

- No hay comparación de modelos en este bloque.
- La colección se detiene y queda `DATA_NOT_VERIFIED` si la API no responde,
  si no hay resultados finales, o si el archivo de salida ya existe.
- Tras una descarga válida se auditarán total, temporadas, tipos de juego,
  duplicados, marcadores y hash SHA-256. Sólo entonces se pre-registrará el
  experimento E12 separado.
