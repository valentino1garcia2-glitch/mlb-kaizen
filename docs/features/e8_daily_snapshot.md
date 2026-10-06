# Snapshot diario de features E3+E7+E8

Implementación: `mlb_kaizen.features.e8_daily_snapshot`  
Esquema: `e3_e7_e8_daily_features_v1`  
Fórmulas: `run_profile_formula_v1`, `opponent_strength_formula_v1`,
`recent_form_formula_v1`

## Propósito

Construye y guarda el vector ordenado de 13 inputs que consume el artefacto
E3+E7+E8/E11 para un partido futuro. No entrena, no recalibra y no completa
valores ausentes.

## Regla temporal

La predicción debe ocurrir antes del inicio programado. Sólo entran resultados
finales con inicio estrictamente anterior a la predicción y cuyo
`retrieved_at` sea igual o anterior a ella. Un resultado del mismo partido,
una fuente descargada después del instante de predicción o un partido ya
iniciado causan un error explícito.

El `source_timestamp` persistido es el máximo `retrieved_at` de todas las
fuentes crudas usadas, incluido el schedule del partido. Por contrato es
menor o igual que `prediction_timestamp`; así una fila posterior puede
verificar qué información estaba disponible.

## Persistencia

Cada vector se añade a `inference_feature_snapshots` de SQLite. No se
sobrescribe una captura anterior del mismo juego: las múltiples ventanas
pregame son evidencia distinta. El payload conserva el orden exacto requerido
por el artefacto E11.

## Límites actuales

El llamador debe proporcionar resultados finales verificados y un `Game`
pregame. La captura en vivo y la selección del artefacto confiable son pasos
operativos separados; usar resultados descargados retrospectivamente para
recrear una predicción antigua está prohibido por el contrato temporal.
