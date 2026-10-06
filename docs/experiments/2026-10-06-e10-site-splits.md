# E10 — Rendimiento previo separado en casa y visita

## Pregunta

¿El rendimiento de un club en casa o de visita, según corresponda al próximo
partido, añade información al modelo E3+E7+E8?

## Diseño fijado antes de evaluar

- Fuente: colección normalizada local de MLB, 2022–2026.
- Para el local: carreras anotadas y permitidas en sus partidos previos como
  local. Para el visitante: las mismas tasas en sus partidos previos como
  visitante.
- Los acumuladores se reinician por equipo al comenzar una temporada.
- Se exigen cinco partidos anteriores en la condición correspondiente.
- Control: E3+E7+E8 sobre exactamente las mismas filas E10.
- Candidato: control más cuatro índices de condición casa/visita.
- Selección: entrenar 2022–2024 y medir 2025.
- Test 2026: abrir una sola vez únicamente si Brier y log loss mejoran ambos
  en 2025.
- Si 2025 falla, documentar y no usar 2026 para rescatar la hipótesis.

## Salvaguardas

Cada acumulador se consulta antes de actualizarse con el partido actual. Las
pruebas cubren contrato de fórmula, marcador propio, resultado futuro y el
umbral mínimo.

## Resultado

### FACT

E10 produjo 10,684 filas. Validación: 6,468 filas de entrenamiento (2022–2024)
y 2,165 de evaluación (2025). Test final: 8,633 de entrenamiento (2022–2025)
y 2,051 de evaluación (2026).

| Corte | Modelo | Brier | Log loss | MAE local | MAE visitante |
| --- | --- | ---: | ---: | ---: | ---: |
| Validación 2025 | Control E3+E7+E8 | 0.244756 | 0.682480 | 2.394260 | 2.617112 |
| Validación 2025 | E10 + casa/visita | **0.244732** | **0.682419** | **2.391289** | **2.605609** |
| Test 2026 | Control E3+E7+E8 | **0.245138** | **0.683306** | 2.443264 | 2.536562 |
| Test 2026 | E10 + casa/visita | 0.245231 | 0.683501 | **2.440652** | **2.534578** |

### INTERPRETACIÓN Y DECISIÓN

La mínima mejora de 2025 habilitó el único test de 2026, pero no se repitió:
Brier y log loss empeoraron. **DISCARD para el modelo activo.** Una menor MAE
de carreras no sustituye la regla establecida para las probabilidades.

Este resultado es evidencia contra esta representación concreta, no contra la
idea general de que jugar casa/visita importe en MLB. No se reajustan umbrales
ni se vuelve a probar 2026 para rescatarla.
