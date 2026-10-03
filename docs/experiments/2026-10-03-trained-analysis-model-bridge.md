# Puente entre modelo entrenado y Analyst Mode — 2026-10-03

## Objetivo

Evitar que Analyst Mode use una fórmula fija distinta del modelo E3 evaluado
históricamente.

## Implementación

`TrainedPoissonAnalysisModel` adapta los perfiles actuales de equipo al
contrato E3 y puede cargar sólo artefactos locales confiables que sean
`PoissonRunModel`. `AnalysisService` acepta ese adaptador y un calibrador
opcional, conservando tanto probabilidad cruda como calibrada.

## Protecciones

- Rechaza artefactos que no sean el modelo Poisson soportado.
- Rechaza modelos que pidan variables distintas del contrato E3 disponible.
- La fórmula fija sigue siendo el fallback cuando no hay artefacto.
- Incluso con calibración, el resultado continúa marcado `EXPERIMENTAL`.

## Pendiente

Exponer la selección de artefacto y calibrador de confianza en el comando de
análisis antes de iniciar el experimento de lineups.
