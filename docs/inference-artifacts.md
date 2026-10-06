# Artefacto de inferencia E3+E7+E8/E11

El comando `train-e11-inference` crea un único artefacto local confiable que
contiene el Poisson final E3+E7+E8 y su calibrador Platt E11. Reutiliza la
persistencia existente de artefactos (`.pkl` más `.json`); no descarga ni
reentrena nada al predecir.

El archivo de metadatos declara esquema, experimento, versión de
preprocesamiento, fecha máxima de entrenamiento y las 13 features en su orden
exacto. `predict-e11-inference` carga ese paquete y exige un objeto JSON con
las mismas 13 claves en el mismo orden. Features faltantes, extras, orden
distinto, esquema incompatible o valores no numéricos fallan explícitamente.

La persona que genera el vector diario debe proveer E7 y E8 con información
point-in-time. El artefacto no inventa ni reconstruye esas features y no usa
el modelo fijo de Analyst Mode como sustituto silencioso.

Ejemplo conceptual:

```text
train-e11-inference \
  --training-dataset dataset_2022_2025.jsonl \
  --calibration-training-dataset dataset_2022_2024.jsonl \
  --calibration-dataset dataset_2025.jsonl \
  --output artifacts/e3-e7-e8-e11

predict-e11-inference \
  --artifact artifacts/e3-e7-e8-e11 \
  --features pregame_e3_e7_e8_features.json
```

## Flujo diario conectado

`daily-e11-inference` conecta la fuente MLB ya existente con el snapshot y el
artefacto. Requiere una fecha, el identificador exacto del juego, el inicio
del histórico de resultados y una ruta explícita al artefacto confiable:

```text
daily-e11-inference \
  --date 2026-10-20 \
  --game-id mlb:123456 \
  --history-start 2022-03-01 \
  --artifact artifacts/e3-e7-e8-e11
```

El comando consulta el calendario y los resultados finales disponibles,
verifica que el juego no haya empezado, construye el vector E3+E7+E8 y lo
guarda append-only. Luego carga —sin reentrenar— el artefacto E11 y persiste
la predicción cruda y calibrada. Si falta historia, el juego no pertenece al
calendario solicitado, una fuente llegó tarde o el partido ya inició, falla
sin escribir una predicción.

La historia se consulta en bloques de fechas no solapados: el endpoint público
de MLB puede truncar una consulta de varios años. Una respuesta parcial no se
acepta como historial suficiente para una feature diaria.

`data_quality=1.0` en ese registro significa únicamente que se cumplieron los
requisitos estrictos del vector de entrada; no cambia el estado experimental
del modelo ni significa calidad predictiva perfecta.

La inferencia permanece experimental: este contrato garantiza reproducibilidad,
no validación de producción ni rentabilidad.
