# Registro incremental de experimentos

## Recuperación E2–E5 — 2026-10-03

| ID | Cambio | Comparación justa | Resultado |
| --- | --- | --- | --- |
| E2/E2b | ERA del abridor, point-in-time | Referencia ingenua, 2026 | Sin mejora medible; E2b = 0.2490, igual a referencia |
| E3 | Regularización Poisson `alpha=0.0001` | 2022–2024/2025 para elegir; 2026 intacto | Brier 0.2463 vs 0.2490 de referencia |
| E4 | Factor empírico de parque | Mismas 2,312 filas | 0.2459 con y sin parque |
| E5 | ERA acumulado de bullpen | Mismas 2,322 filas | 0.2459 vs 0.2460; diferencia no concluyente |

Solo E3 se conserva como mejora demostrada. E2, E4 y E5 quedan como
experimentos negativos: su código permite volver a examinarlos, pero no deben
presentarse como una ventaja predictiva comprobada.
