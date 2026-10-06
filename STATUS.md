# STATUS.md — MLB KAIZEN checkpoint

fecha: 2026-10-03
commit: 64b4aa5

## Integración de recuperación — 2026-10-03

- Fuente integrada: `MLB_KAIZEN.zip`, SHA-256 `AB8EF5B1008D3F120D4803837DB9B974618C4163F77BB9B09A39041CE770F25C`.
- Historial del archivo fuente: último commit verificado `e12e17a`; su checkpoint registra una evaluación real del 2026-09-19.
- Validación de esta copia integrada: 81/81 PASS con `unittest` usando dependencias locales (`scikit-learn` y `jsonschema`).
- Esta recuperación sustituye la foundation y el fragmento aislado de Claude como fuente operativa. El fragmento permanece documentado únicamente como procedencia histórica.
- La rama actual de integración preserva `master` sin modificar hasta que este bloque quede registrado y publicado.

## Lectura rápida

El repositorio ya contiene la **implementación de las ocho fases funcionales principales** del flujo,
pero no debe interpretarse como "modelo empíricamente validado" todavía. Hay dos tipos de estado:

- **Engineering status:** si el código/infraestructura de una fase existe y está probado.
- **Evidence status:** si ya existe evidencia real (proveedores vivos, históricos point-in-time,
  backtest y calibración) que permita afirmar comportamiento predictivo fuera de muestra.

## Fases

| Fase | Engineering | Evidence / dependencia externa |
|---|---|---|
| 1 — Foundation | DONE | DONE |
| 2 — Contratos, schema y migraciones | DONE | DONE |
| 3 — Proveedores y snapshots | IMPLEMENTED / LIVE VERIFY PENDING | `odds` y `weather` requieren verificación viva; Statcast no es requisito del camino mínimo actual |
| 4 — Feature Store v1 | DONE | Los fixtures cubren la fórmula; validar fuentes históricas reales antes de backtest |
| 4.5 — Analyst Mode | DONE | Smoke test local completado |
| 5 — Baseline entrenable | DONE (Poisson + artefactos) | REAL DATA: primera evaluación corrida (2026-09-19), ver abajo |
| 6 — Walk-forward + calibración | DONE (framework temporal) | REAL DATA: primera evaluación corrida (2026-09-19), ver abajo |
| 7 — ML challenger | DONE (Random Forest) | REAL DATA: primera evaluación corrida (2026-09-19), ver abajo |
| 8 — Interfaz / tracking / reportes | DONE (core) | CLV histórico requiere snapshots de apertura/cierre reales |

### Conteo

```text
Engineering implementation: 8 / 8 fases cubiertas
Empirical validation:       0 / 8 fases con evidencia histórica completa
External/live verification: pendiente en proveedores
```

La segunda cifra **no significa que el código no funcione**; significa que todavía no se ha aportado
un dataset histórico real con timestamps suficientes para afirmar rendimiento predictivo.

## Primera evaluación real (2026-09-19)

Dataset real auditado (12,045 partidos únicos, 2022-2026, ver HANDOFF.md sección 21) →
11,836 filas point-in-time (`data/historical/2022_2026_point_in_time.jsonl`) → walk-forward
real (`data/evaluation/first_real_evaluation_2026-09-19.md`):

```text
                    Brier    Log loss
Referencia ingenua  0.2490   0.6912
Poisson baseline    0.2494   0.6919
Random Forest       0.2542   0.7026
```

**Ninguno de los dos modelos supera de forma clara a la referencia ingenua** (predecir
siempre la tasa histórica de victoria local). El pipeline corre de punta a punta sin fuga
temporal sobre datos reales — la conclusión honesta es que las features actuales (solo
carreras anotadas/permitidas, sin pitcher/parque/rival) no muestran ventaja predictiva
medible todavía. No hay `MODEL: VALIDATED` en ningún camino de código — sigue correcto que
no lo haya.

## Estado actual del pipeline

```text
LIVE / SNAPSHOT / MANUAL / HYBRID INPUT
                ↓
          QUALITY ASSESSMENT
                ↓
         TEAM RUN PROFILE v1
                ↓
        TRANSPARENT BASELINE
                ↓
          MONTE CARLO
                ↓
       MARKET vs MODEL
                ↓
       MACHINE PICK (PRELIMINARY)
                ↓
          HUMAN PICK
                ↓
       RESULT / TRACKING
                ↓
      WALK-FORWARD BACKTEST
                ↓
          CALIBRATION
                ↓
        ML CHALLENGER
```

## Funcionalidades terminadas en este checkpoint

- Separación de `CalculationStatus`, `DataQualityStatus` y `ModelValidationStatus`.
- Analyst Mode con `live`, `snapshot`, `manual` y `hybrid`.
- Pitcher/lineup/odds incompletos pueden quedar advertidos sin impedir el cálculo cuando matemáticamente
  el input suministrado es suficiente.
- `TeamRunProfile` normalizado y persistido como snapshot.
- JSON Schema para la entrada de análisis.
- Mercado soportado: moneyline, total y run line.
- No-vig, edge y EV preliminar.
- Salida `machine_pick` explícitamente `preliminary` cuando el modelo es experimental.
- Registro persistente de pick humano, pick máquina y resultado.
- Reporte de texto y HTML con comparación Humano vs Máquina.
- PnL realizado cuando las selecciones incluyen cuotas decimales.
- Dataset histórico JSONL point-in-time.
- Entrenamiento Poisson regularizado.
- Challenger Random Forest.
- Walk-forward expanding window.
- Calibración temporal post-hoc separada.
- Artefactos versionados con metadatos.
- Verificación dirigida por impacto mediante `scripts/verify.py`.
- `AGENTS.md` + `CLAUDE.md` + `AI_REPO_MAP.md` para reducir relecturas y uso redundante de contexto.
- Protocolo de cloud/subagents documentado en `docs/AI_CLOUD_AGENTS.md`.

## Bloqueos reales que todavía requieren datos externos

1. **SportsGameOdds:** el adaptador existe, pero una prueba viva requiere una API key y red. La
   documentación actual describe `/v2/events`, `leagueID=MLB`, `oddsAvailable`, `oddID` y precios por
   bookmaker; el código usa `x-api-key` para que la credencial no quede en la URL/cache. Sus términos
   actuales contienen restricciones de uso, rate limits y condiciones específicas para ML que deben
   respetarse antes de producción. No marcar como verificado hasta probarlo realmente.
2. **MLB team stats / run profile:** el parser tiene fixtures de forma realista, pero falta una prueba
   viva en este entorno.
3. **NWS weather:** estructura cubierta por tests; falta fetch vivo en este entorno.
4. **Histórico point-in-time:** RESUELTO 2026-09-19 — dataset real (12,045 partidos, 2022-2026,
   auditado en HANDOFF.md sección 21) ingresado y evaluado. Ver "Primera evaluación real" arriba.
   Lo que sigue pendiente no es conseguir datos, sino mejorar features (pitcher/parque/rival) para
   que el modelo supere a la referencia ingenua.

## E7 — fuerza previa de rivales (2026-10-05)

**FACT:** E6 sigue bloqueado por los lineups históricos, pero los resultados
históricos existentes sí permiten medir qué tan exigentes fueron los rivales
que cada equipo ya enfrentó. E7 añade esa señal sin usar marcador propio ni
futuro. Elegida sólo con 2025 (entrenamiento 2022–2024), baja Brier de
0.245522 a 0.245235 y log loss de 0.684097 a 0.683492 contra E3 sobre las
mismas filas. El único test de 2026 repite la mejora: Brier 0.245949 a
0.245633 y log loss 0.684965 a 0.684313 (2,283 partidos).

**INTERPRETACIÓN:** es una mejora pequeña pero consistente; se conserva como
señal experimental, no como validación de producción ni promesa de ganancia.
El detalle y el control equivalente están en
`docs/experiments/2026-10-05-e7-opponent-strength.md`.

**Próxima acción:** diseñar y evaluar una sola versión point-in-time de forma
reciente (ventana móvil), comparada contra E3+E7 en las mismas filas. No tocar
E6-B hasta tener historial de lineups verificablemente pregame.

## Última verificación

```text
126 / 126 PASS
```

Comando:

```bash
python3 -m unittest discover -s tests -t . -v
```

Compilación:

```bash
python3 -m compileall -q mlb_kaizen tests scripts
```

Smoke funcional con dataset sintético/demo (histórico) más la evaluación real 2026-09-19
(ver arriba) sobre datos reales:

- `train-model --model poisson` → artefacto creado.
- `backtest --model compare --calibrate` → Poisson + RF + calibración temporal.
- `analyze --mode manual --persist` → números visibles aun con modelo `EXPERIMENTAL`.
- `record-human-pick` + `record-result` + `leaderboard` → flujo Humano vs Máquina.
- `leaderboard --format html` → reporte con barras comparativas.
- `scripts/ingest_external_collector.py` → 11,836 filas reales point-in-time.

Los números del smoke con dataset sintético son **solo prueba de ejecución**; los de la
sección "Primera evaluación real" arriba sí son sobre partidos MLB reales.

## Próxima acción recomendada

El siguiente experimento controlado es una ventana de forma reciente
point-in-time, comparada contra E3+E7. E6-B sigue bloqueado hasta obtener
lineups históricos con evidencia pregame.

```text
usar probable_pitchers (ya en el dataset, sin usar en features)
→ factor de parque
→ ventana móvil de forma reciente en vez de temporada completa acumulada
→ ajuste por fuerza del rival
→ recalibración de probabilidad (Platt/isotonic)
→ volver a correr walk-forward y comparar contra esta baseline real (Brier 0.2490-0.2494)
```

## Recuperación E2–E5 — 2026-10-03

E3 corrigió la regularización del modelo Poisson y logró Brier 0.2463 frente
a 0.2490 de la referencia en 2026. Pitcher, parque y bullpen no añadieron una
mejora incremental demostrable.

## Diagnóstico de calibración — 2026-10-03

Completado. El modelo E3 distingue partidos mejor que elegir siempre al local,
pero sus probabilidades quedan comprimidas hacia 50%. Una calibración temporal
basada en 2025 mejora Brier de 0.2463 a 0.2462 al medir 2026: mejora pequeña,
todavía no validación de producción. Analyst Mode usa una fórmula fija distinta
del modelo entrenado; antes de lineups debe cargar un artefacto entrenado de
forma versionada.

## Puente al modelo entrenado — 2026-10-03

Analyst Mode ya puede recibir un artefacto local confiable del modelo Poisson
E3 y un calibrador opcional, conservando la fórmula fija como fallback. La
salida continúa etiquetada como experimental.

## Selección temporal de calibración — 2026-10-03

Platt superó a la calibración por rangos usando 2024 para ajustar y 2025 para
elegir el método. Reajustada con 2025 y medida por primera vez en 2026, mejora
Brier de 0.2463 a 0.2462. Sigue siendo una mejora pequeña y permanece separada
de Analyst Mode hasta que éste use el modelo entrenado E3.

## Modelo entrenado desde el comando — 2026-10-03

El comando `analyze` ahora acepta un modelo Poisson entrenado local mediante
`--trained-model` y, si existe, su calibrador Platt mediante `--calibrator`.
Ambos son opcionales y solo se cargan desde archivos locales confiables. Incluso
con los artefactos, el informe sigue marcado como **experimental**: conecta el
trabajo evaluado con el análisis diario, pero no afirma validación de producción.
Suite: 120/120.

## Auditoría pre-E6 — 2026-10-03

E0--E5 fueron auditados sin reentrenar ni ajustar parámetros. E3 mantiene la
única mejora medible: la reducción de regularización permitió usar la señal de
equipo ya presente. Los resultados nulos de bullpen y parque se explican sobre
todo por información ya absorbida por prevención de equipo; el abridor conserva
una explicación abierta de representación/modelo. E3 sí separa partidos, pero
subestima la tasa local media (50.43% predicho frente a 53.11% observado) y
permanece comprimido hacia 50%; Platt mejora sólo de 0.2463 a 0.2462 Brier.

**Decisión: READY_FOR_E6**, sólo para auditar y diseñar un dataset histórico de
lineup con timestamps anteriores al partido. No se implementa E6 en este bloque,
ni se etiqueta el modelo como validado o rentable. Detalle reproducible en
`docs/experiments/2026-10-03-pre-e6-audit.md`.

## E6-A — Auditoría de temporalidad de lineups — 2026-10-03

**E6_DATA_BLOCKED.** Las 12,045 partidas históricas disponibles contienen cero
lineups completos y cero timestamps que prueben disponibilidad antes del juego.
Los archivos raw son schedules/resultados finales con estado dentro del juego,
no alineaciones iniciales; la descarga actual de boxscores pasados sería
postpartido. El proveedor y el diseño de snapshots sí permiten capturar lineups
futuros, pero sólo serán válidos si `retrieved_at < game_start_time`. No se
construye E6-B hasta obtener o capturar ese histórico. Ver
`docs/experiments/2026-10-03-e6a-lineup-temporality-audit.md`.

## Recuperación después de agotar contexto

Leer solamente:

```text
AGENTS.md
CLAUDE.md
STATUS.md
.agent/checkpoint.json
```

y usar `docs/AI_REPO_MAP.md` para localizar el módulo relevante. Abrir `HANDOFF.md` solo si el checkpoint
no alcanza.
