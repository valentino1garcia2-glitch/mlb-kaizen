# E12-A — Viabilidad de un modelo de playoffs

## Pregunta

¿Hay datos oficiales suficientes para evaluar un modelo de playoffs separado,
sin presentar el modelo de temporada regular como si ya estuviera validado para
postemporada?

## FACT

La colección que entrenó E3+E7+E8 contiene solamente `game_type: R`
(temporada regular). MLB reporta playoffs con códigos `F`, `D`, `L` y `W`.

| Temporadas | Juegos finales de playoffs |
| --- | ---: |
| 2022–2025 disponibles en el corte actual | 169 |
| 2012–2025, auditados por conteo oficial | 530 |

Los 169 juegos actuales no son suficientes para ajustar, seleccionar y probar
un modelo de 13 inputs más calibración. Los 530 de 2012–2025 permiten una
investigación simple con cortes temporales, pero los tests anuales recientes
(~43 juegos) seguirán siendo pequeños: una mejora aislada no autorizará uso
para apuestas.

## Decisión de seguridad

Mientras no exista E12 evaluado por separado, `daily-e11-inference` admite
únicamente `game_type: R`. Cualquier código de playoffs o código ausente falla
explícitamente. La captura Dodgers @ Braves previa a esta protección queda
como smoke técnico del pipeline, no como evidencia del modelo regular.

## Siguiente etapa

Crear un dataset local y versionado de resultados oficiales 2012–2025 que
incluya tanto temporada regular como playoffs y conserve `game_type`. Las
features de cada playoff se construirán sólo con resultados anteriores a ese
juego. Antes de entrenar se fijará el corte temporal, control, métricas y
criterio de parada; no se reutilizará la calibración E11.

## Interpretación

El conteo demuestra viabilidad de investigación, no suficiencia para declarar
un modelo de playoffs fiable. La principal conclusión actual es operativa:
separar ambas fases evita mezclar evidencia no comparable.
