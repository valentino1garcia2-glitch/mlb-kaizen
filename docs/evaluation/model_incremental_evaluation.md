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

## Auditoría pre-E6 — 2026-10-03

La auditoría completa está en
[`docs/experiments/2026-10-03-pre-e6-audit.md`](../experiments/2026-10-03-pre-e6-audit.md).
La decisión es **READY_FOR_E6** únicamente para auditar/diseñar datos de
lineup point-in-time. E3 sigue siendo la referencia; E2, E4 y E5 no se
reclasifican como mejoras, y no se afirma validación ni rentabilidad.

## E6-A — Disponibilidad temporal de lineups — 2026-10-03

Auditoría completada en
[`docs/experiments/2026-10-03-e6a-lineup-temporality-audit.md`](../experiments/2026-10-03-e6a-lineup-temporality-audit.md).
Resultado: **E6_DATA_BLOCKED**. Las 12,045 partidas históricas auditadas tienen
0 lineups, 0 timestamps de lineup utilizables y 0 confirmaciones pregame. No
se inicia E6-B hasta recibir/capturar evidencia temporal válida.

## E7 — Fuerza previa de rivales — 2026-10-05

E6 permanece bloqueado por falta de timestamps pregame de lineups. E7 usa
solamente resultados históricos ya disponibles antes de cada partido: la
calidad acumulada de los rivales que cada club ya enfrentó. El protocolo,
salvaguardas y resultados completos viven en
[`2026-10-05-e7-opponent-strength.md`](../experiments/2026-10-05-e7-opponent-strength.md).

En comparación justa sobre las mismas filas, el control E3 pasa de Brier
0.245522 a 0.245235 en validación 2025 y de 0.245949 a 0.245633 en el test
final 2026; log loss también baja en ambos cortes. **Decisión: KEEP como
señal experimental**, aún no como modelo validado ni ventaja rentable.

## E8 — Forma reciente — 2026-10-06

E8 añade ofensiva y prevención de los 15 partidos previos de la misma
temporada; no transporta forma del año anterior. En la cohorte común E8, Brier
bajó de 0.245308 a 0.244775 en la validación 2025 y de 0.245277 a 0.245110 en
el test final 2026; log loss también disminuyó en ambos. **Decisión: KEEP como
señal experimental**, no validación de producción ni ventaja rentable. El
protocolo y evidencia están en
[`2026-10-06-e8-recent-form.md`](../experiments/2026-10-06-e8-recent-form.md).

## E9 — Días de descanso — 2026-10-06

E9 derivó días completos sin jugar desde el calendario anterior, sin fuentes
externas ni leakage. Frente a E3+E7+E8 en la validación 2025, Brier empeoró de
0.244775 a 0.244870 y log loss de 0.682519 a 0.682720. **Decisión: DISCARD**;
no se abrió 2026. Registro completo:
[`2026-10-06-e9-rest-days.md`](../experiments/2026-10-06-e9-rest-days.md).
