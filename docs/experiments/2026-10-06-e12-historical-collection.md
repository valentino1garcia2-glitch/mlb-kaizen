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

## Resultado de la colección — FACT

La colección se completó con el archivo local ignorado por Git
`data/external/mlb_results_2012_2025.jsonl`.

| Control | Resultado |
| --- | ---: |
| Resultados finales | 39,346 |
| IDs únicos | 39,346 |
| Marcadores negativos | 0 |
| Tipos desconocidos | 0 |
| Juegos `R` | 32,408 |
| Juegos de playoffs `F` + `D` + `L` + `W` | 547 |
| SHA-256 | `38ff5c24f35f7bce4bb5f7fb16e6368307aeb54c23d97a662da85183c3302b1f` |

Cobertura por año: 2012 2,961; 2013 2,997; 2014 2,912; 2015 2,956;
2016 2,940; 2017 3,013; 2018 2,955; 2019 2,934; 2020 1,268; 2021 2,868;
2022 2,724; 2023 2,946; 2024 2,932; 2025 2,940. La caída de 2020 es
consistente con la temporada regular reducida; no se imputó ningún partido.

Los demás tipos se conservaron para auditoría, pero no son candidatos por
defecto para E12: `S` 6,167, `E` 211 y `A` 13. El conteo anterior de 530
playoffs fue una consulta preliminar; el archivo final y reproducible contiene
547. Esta cifra sustituye al conteo preliminar para el diseño posterior.

## Decisión

**E12_DATA_READY_FOR_DESIGN.** Hay resultados oficiales suficientes para
diseñar un experimento de playoffs estrecho y separado. No significa que haya
suficiente evidencia para apostar ni que el modelo regular sea válido en
playoffs. El siguiente paso es pre-registrar el filtro de tipos, las features,
los cortes temporales y el criterio de parada antes de construir filas o
entrenar.
