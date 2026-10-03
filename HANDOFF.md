# Handoff — MLB KAIZEN

Este documento permite que otra IA o ingeniero continúe el proyecto sin tener
que reconstruir el contexto de la conversación.

## 1. Objetivo del proyecto

Construir **MLB KAIZEN**, una plataforma local de análisis cuantitativo de MLB
orientada a investigación y evaluación de mercados deportivos. No debe ser un
script que fuerce picks: un resultado válido es `NO BET`, `DATA_INCOMPLETE` o
`MODEL_UNCALIBRATED`.

El producto final debe poder:

- consultar y conservar datos de MLB con fuente, timestamp y estado;
- modelar carreras, moneyline, totales y run line;
- incorporar pitchers, bullpen, ofensiva, defensa, parque, clima y lineups
  únicamente cuando esos datos sean verificables;
- convertir cuotas, quitar vig de forma etiquetada, calcular edge, EV y CLV;
- simular distribuciones de carreras;
- hacer backtests walk-forward sin leakage;
- guardar predicciones inmutables y sus resultados;
- explicar incertidumbre y no presentar estimaciones como hechos.

El idioma de reportes y UX es español. Identificadores, código y nombres de
bibliotecas permanecen en inglés.

## 2. Restricciones no negociables

Estas reglas son más importantes que añadir funcionalidades rápidamente.

1. **No inventar** estadísticas, cuotas, lesiones, lineups, pitchers,
   movimientos de mercado, respuestas de API, resultados de backtest ni
   rendimiento de modelos. Cuando algo no puede verificarse, mostrar
   `DATA NOT VERIFIED` o el estado correspondiente.
2. Mantener separados datos observados, estimación del modelo, precio de
   mercado, valor calculado y resultado real.
3. Para una predicción histórica en tiempo `T`, usar solo información que
   existiera antes de `T`. No usar lineups finales, cuotas de cierre, Statcast
   postpartido, lesiones futuras, rosters futuros ni estadísticas revisadas.
4. La calibración para decisiones de EV debe ser temporal y out-of-sample.
   No calibrar y evaluar sobre las mismas observaciones.
5. No modificar predicciones históricas cuando cambie el modelo. Versionar
   modelo, features, calibración, configuración, timestamps y semilla.
6. Los resultados de apuestas o el win rate de picks del usuario nunca deben
   alterar la fuerza estimada de un equipo. Sirven para evaluar estrategia,
   no como feature deportiva.
7. Antes de añadir un proveedor externo, comprobar existencia, campos,
   autenticación, límites, licencia/uso y frescura. Usar adaptadores para no
   acoplar la aplicación a una respuesta de API.
8. Un modelo más complejo, red neuronal, ensemble o más simulaciones solo se
   añade si demuestra mejora temporal fuera de muestra.

## 3. De dónde viene el proyecto

El usuario aportó un notebook NBA KAIZEN de Colab. El notebook era una fuente
de inspiración de UX, tracking y gráficos, pero no una base estadística apta
para trasladar literalmente a MLB.

Hallazgos relevantes de la auditoría NBA:

- Mezclaba 90% últimos 10 juegos y 10% temporada sin validación.
- Aplicaba ajustes fijos de B2B, playoffs, H2H, localía y bankroll.
- Cambiaba el `OffRtg` según el resultado histórico de apuestas por equipo:
  sesgo de selección y bucle de retroalimentación que no debe reutilizarse.
- Llamaba “ML” a una `IsotonicRegression`; eso era calibración sobre picks,
  no un modelo de partido entrenado correctamente.
- Reconstruía probabilidades desde EV y cuotas, tenía cuota fija 1.90 en
  varios cálculos y no separaba mercados ni evaluación temporal.
- Usaba datos agregados, H2H y logs actuales sin snapshots point-in-time;
  eso hace vulnerable cualquier backtest al leakage.
- Dependía de celdas globales, Excel, rutas hardcodeadas, parsing de texto y
  `except:` silenciosos.

Ideas que sí se conservaron: flujo guiado, tracking, reportes claros,
visualización y separación entre análisis y staking.

## 4. Estado actual: versión 0.1.0

Se implementó un **vertical slice de foundation**, no un sistema MLB terminado.
Existe código funcional y testeado para:

| Área | Estado | Qué hace |
|---|---|---|
| Configuración | Hecho | `Settings` centralizados por variables de entorno. |
| Dominio y procedencia | Hecho | `Game`, `DataProvenance`, estados de disponibilidad, perfiles de carrera. |
| HTTP/caché | Hecho | timeout, reintentos, caché de respuestas exitosas y error `DATA NOT VERIFIED`. |
| Calendario MLB | Hecho | Adaptador a `statsapi.mlb.com` para schedule, detrás de interfaz. |
| Persistencia | Hecho | SQLite append-only para snapshots de juegos, cuotas y predicciones. |
| Validación | Hecho | Puerta de calidad: pitchers, lineups y odds desconocidos bloquean señal. |
| Mercado | Hecho | American→decimal, implied probability, no-vig proporcional, edge, EV y Kelly. |
| Modelo base | Hecho | Fórmula transparente de carreras esperadas. No está entrenada. |
| Simulación | Hecho | Negativa Binomial reproducible con semilla y error de Monte Carlo. |
| Reporte/CLI | Hecho | CLI de salud, calendario, inicialización y análisis desde JSON. |
| Tests | Hecho | 9 pruebas unitarias/integración local, todas pasan. |
| Statcast, lineups, bullpen, clima | Pendiente | No agregar datos ficticios ni adaptadores no verificados. |
| Odds en vivo | Pendiente | Hay contrato/persistencia, no proveedor implementado. |
| Features reales | Pendiente | Los perfiles actuales deben venir de un feature store futuro. |
| Entrenamiento/calibración/backtest | Pendiente | Es requisito antes de cualquier señal. |
| Dashboard visual | Pendiente | La CLI es la interfaz inicial. |

## 5. Estructura real del repositorio

```text
MLB KAIZEN/
├── README.md
├── HANDOFF.md                         # este archivo
├── pyproject.toml
├── .gitignore
├── docs/
│   └── analysis-input.md              # contrato de JSON para el comando analyze
├── mlb_kaizen/
│   ├── config/settings.py
│   ├── domain/models.py
│   ├── data/http.py
│   ├── data/providers.py
│   ├── data/mlb_stats.py
│   ├── market/odds.py
│   ├── models/baseline.py
│   ├── simulation/monte_carlo.py
│   ├── validation/quality.py
│   ├── storage/database.py
│   ├── services/analysis.py
│   ├── reporting/text.py
│   └── interface/cli.py
└── tests/
    ├── test_analysis_service.py
    ├── test_baseline_and_simulation.py
    ├── test_database.py
    ├── test_mlb_stats.py
    ├── test_odds.py
    └── test_quality.py
```

La arquitectura objetivo más amplia incluye `features/`, `backtesting/`,
`tracking/`, `visualization/` e interfaces adicionales. No crear módulos vacíos
solo para hacer coincidir el árbol: añadirlos junto con una responsabilidad y
tests concretos.

## 6. Funcionamiento actual, explicado con precisión

### 6.1 Datos y calendario

`mlb_kaizen.data.mlb_stats.MLBStatsProvider` obtiene juegos del endpoint de
calendario de MLB usando `CachedHttpClient`. Cada `Game` tiene un ID con prefijo
`mlb:`, timestamp de recuperación, fuente y URL. El adaptador fue probado en
vivo para `2026-09-16`: recuperó 15 juegos y los almacenó como snapshots.

No asumir que el endpoint tiene documentación oficial contractual. La
documentación pública localizada es comunitaria. Mantener el proveedor detrás
de `ScheduleProvider` y registrar cualquier fallo como no verificado.

### 6.2 Modelo base

Archivo: `mlb_kaizen/models/baseline.py`.

El modelo usa dos índices normalizados que debe producir un pipeline de
features posterior:

```text
home_expected_runs = league_runs_per_team
                     × home_offensive_index
                     × away_run_prevention_index
                     × home_advantage_multiplier

away_expected_runs = league_runs_per_team
                     × away_offensive_index
                     × home_run_prevention_index
```

Valores por defecto:

- `league_runs_per_team = 4.40`
- `home_advantage_multiplier = 1.035`
- `dispersion = 4.0`

Estos valores son **supuestos de configuración**, no resultados entrenados ni
afirmaciones de que funcionen en 2026. Deben compararse mediante backtest
walk-forward contra alternativas Poisson y Negativa Binomial.

`TeamRunProfile` exige identificador de equipo, tamaño de muestra, calidad de
datos, índices positivos y procedencia. No crear perfiles “de ejemplo” para
producir picks reales.

### 6.3 Simulación

Archivo: `mlb_kaizen/simulation/monte_carlo.py`.

La simulación usa una mezcla Gamma-Poisson, equivalente a Negativa Binomial,
para permitir sobredispersión de carreras. Reporta media de carreras,
probabilidad de victoria, total, run line, empates regulatorios y error de
muestreo Monte Carlo.

Limitación explícita: los empates regulatorios se resuelven con un proxy
simétrico 50/50 de extra innings y se reportan por separado. No afirmar que
esto modele extra innings correctamente hasta reemplazarlo o validarlo.

Más simulaciones reducen error de muestreo; no corrigen una mala especificación
del modelo.

### 6.4 Mercado

Archivo: `mlb_kaizen/market/odds.py`.

- Conversión American→Decimal.
- Probabilidad implícita: `1 / decimal_odds`.
- No-vig actual: normalización proporcional. Debe etiquetarse así; no es Shin
  ni power method.
- Edge: `model_probability - market_probability`.
- EV por unidad: `p * (decimal_odds - 1) - (1 - p)`.
- Kelly fraccional: capa independiente del modelo.

No se realiza EV directamente en cuotas americanas. La cuota y su timestamp
deben conservarse por observación, nunca reemplazarse con 1.90 fijo.

### 6.5 Calidad y salida

Archivo: `mlb_kaizen/validation/quality.py` y
`mlb_kaizen/services/analysis.py`.

La puerta de calidad revisa `starting_pitchers`, `lineups` y `odds`. Si faltan,
son desconocidos o la calidad del perfil es baja, devuelve `DATA_INCOMPLETE`.

Incluso con todos los datos disponibles, la versión actual devuelve
`MODEL_UNCALIBRATED`, porque no existe un registro temporal de calibración. El
reporte puede mostrar EV preliminar usando la probabilidad cruda, pero advierte
que **no debe usarse como señal de apuesta**.

## 7. Cómo ejecutar y verificar

Requisito: Python 3.11+. En la sesión de desarrollo inicial Python no estaba
en el `PATH`; se usó el runtime incluido de Codex para verificar el proyecto.
En una instalación normal de Windows, usar `py` o `python` según corresponda.

```powershell
cd "C:\Users\user\Documents\ChatGPT\MLB KAIZEN"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
py -m unittest discover -s tests -t . -v
py -m mlb_kaizen init-db
py -m mlb_kaizen health
py -m mlb_kaizen schedule --date 2026-09-16
```

El comando de calendario necesita red. Si no se puede acceder, debe terminar
en `DATA NOT VERIFIED`, no inventar que no hay juegos.

Verificación realizada en la implementación:

```text
python -m compileall -q mlb_kaizen tests
python -m unittest discover -s tests -t . -v
```

Resultado: **9 pruebas ejecutadas, 9 correctas**. También se ejecutaron
`init-db`, `health` y una consulta real del calendario. La base y la caché se
crean bajo `data/`; están ignoradas por Git.

## 8. Cómo interpretar `analyze`

La CLI admite:

```powershell
py -m mlb_kaizen analyze --input ruta\a\archivo.json --persist
```

El contrato está en `docs/analysis-input.md`. Para aceptar un input exige:

- game ID y IDs de home/away;
- timestamp con zona horaria;
- procedencia y estado de cada dato;
- perfiles compatibles con los equipos del juego;
- cuotas decimales opcionales y líneas opcionales.

No existe todavía un comando que genere automáticamente perfiles de fuerza
real para un juego. Esa ausencia es deliberada: automatizar una estimación con
datos incompletos sería peor que pedir datos verificados o devolver “sin
análisis”.

## 9. Plan de continuación recomendado

Trabajar en este orden. No saltar a modelos complejos.

### Fase 2 — Consolidar foundation y contratos

1. Añadir logging estructurado consistente (timestamp, módulo, operación,
   fuente, game ID, versión de modelo; nunca secretos).
2. Añadir migraciones versionadas de SQLite y tablas para fuentes, lineups,
   perfiles/features, resultados, versiones de modelo y errores.
3. Reemplazar el documento ilustrativo de input con JSON Schema validable.
4. Añadir tests de HTTP cache, errores de proveedor, frescura y datos inválidos.

### Fase 3 — Proveedores y snapshots históricos

1. Verificar fuentes oficiales o legítimas para MLB schedule/game data,
   Statcast, lineups, lesiones, clima y cuotas. Documentar:
   URL, autenticación, límites, licencia, campos, timestamp y política de caché.
2. Implementar cada fuente como adapter independiente que produzca objetos del
   dominio, nunca dicts del proveedor en el resto de la aplicación.
3. Almacenar el valor **y** el momento efectivo/conocido. Diseñar snapshots
   para `T-24H`, `T-6H`, `T-3H`, `T-1H`, `T-30M`, pregame y postgame.
4. Para odds, guardar cada observación de apertura, corriente y cierre; no
   actualizar una sola fila de “cuota actual”.

### Fase 4 — Feature store MLB

Crear una ficha por feature con: nombre, definición, fuente, disponibilidad en
el tiempo, fórmula, missing-value policy, validación, tamaño de muestra y
racional.

Priorizar pocas features bien medidas:

1. Fuerza ofensiva de lineup proyectado/confirmado, con shrinkage.
2. Pitcher abridor: innings/muestra, K-BB%, BB%, calidad de contacto,
   handedness, descanso y estado.
3. Bullpen: calidad y disponibilidad como conceptos separados.
4. Parque y clima solo cuando la fuente sea fiable.

No introducir “últimos N juegos” con pesos arbitrarios. Comparar full season,
EWMA y shrinkage empírico mediante validación temporal.

### Fase 5 — Baseline entrenable y validado

1. Definir targets separados: carreras, victoria, total y run line.
2. Construir dataset histórico point-in-time desde snapshots, no desde datos
   actuales revisados.
3. Comparar baseline de promedio liga, Poisson y Negativa Binomial.
4. Evaluar MAE/RMSE para carreras; Brier, log loss y calibración para
   probabilidades.
5. Persistir modelos/configuraciones con versiones explícitas.

### Fase 6 — Backtesting y calibración

1. Implementar expanding-window o walk-forward.
2. Congelar el information set por juego y timestamp.
3. Entrenar calibración solo en datos anteriores; evaluar en un bloque posterior.
4. Añadir detección de leakage: lineups tardíos, odds de cierre, resultados,
   Statcast postpartido, roster/injury futuro y revisiones de datos.
5. Medir CLV solo cuando se tengan opening/current/closing timestamps fiables.

No generar `POSITIVE_EXPECTED_VALUE` hasta que estas fases existan y sus tests
demuestren una calibración aceptable.

### Fase 7 — ML, solamente si está justificado

Evaluar regresión regularizada o gradient boosting con time-aware validation.
Conservarlo únicamente si mejora de forma material al baseline en la muestra
out-of-sample y continúa bien calibrado. Redes neuronales son opcionales y no
son prioridad.

### Fase 8 — UX y diagnósticos

Después de que el pipeline sea válido, crear un notebook/CLI mejorado o un
dashboard. Debe mostrar:

- estado y frescura de datos;
- pitchers, lineup, bullpen, parque y clima con fuentes;
- carreras esperadas y distribución;
- probabilidad cruda, calibrada e incertidumbre;
- mercado, no-vig, edge y EV;
- razón de `NO BET`;
- calibración, CLV, PnL, drawdown y desempeño por segmento.

Las gráficas deben responder una pregunta analítica, no decorar el reporte.

## 10. Reglas para la próxima IA

- Leer primero `README.md`, este archivo y los tests antes de modificar código.
- Ejecutar la suite antes y después de cambios.
- No reemplazar el modelo baseline solo por añadir ML; conservarlo como
  benchmark.
- No abrir una conexión directa a una API desde modelos/features; usar
  `data/` y contratos de dominio.
- No guardar secretos en `Settings`, logs o repositorio. Usar variables de
  entorno y documentar solo los nombres de las variables.
- No transformar estados desconocidos a cero ni asumir que lineup proyectado
  significa confirmado.
- No presentar resultados de simulación como precisión del modelo: separar
  incertidumbre Monte Carlo de incertidumbre de modelo.
- Si se añade una fórmula de mercado, documentar variables, unidades,
  supuestos y prueba unitaria.
- Si se añade una feature, incluir prueba de disponibilidad temporal y no
  aceptar datos posteriores al timestamp de predicción.
- Mantener mensajes para el usuario en español claro; código y tipos en inglés.

## 11. Prompt breve de continuación para otra IA

> Continúa el proyecto local `MLB KAIZEN`. Lee `HANDOFF.md`, `README.md` y los
> tests antes de actuar. El objetivo es una plataforma MLB cuantitativa
> reproducible y no un generador de picks. Respeta estrictamente procedencia,
> temporalidad y no fabricación de datos. La versión actual tiene foundation,
> calendario MLB, SQLite, mercado, baseline transparente y simulación, pero
> está deliberadamente `MODEL_UNCALIBRATED`. Implementa el siguiente bloque más
> pequeño y testeable de la Fase 2/3; no añadas ML, una señal de apuesta ni
> estadísticas ficticias. Antes de integrar una fuente externa, verifica sus
> condiciones actuales, campos, límites y uso. Ejecuta pruebas y reporta qué
> cambió, qué se verificó y qué sigue bloqueado.


## 12. Estado al cierre de esta sesión (2026-09-16) — para la próxima IA

Este bloque es un anexo específico y verificable. Todo lo verificado abajo se
comprobó ejecutando código real en esta sesión, no se asume.

### 12.1 Verificación de entorno hecha en esta sesión

```text
python3 -m compileall -q mlb_kaizen tests   -> OK
python3 -m unittest discover -s tests -t . -v   -> 23/23 OK
```

`pytest` no estaba disponible sin red en el sandbox de esta sesión; se usó
`unittest discover` como en el resto del HANDOFF. Si `pip install -e ".[dev]"`
falla por aislamiento de build sin red, usar:
`pip install -e . --no-build-isolation` (requiere que `setuptools>=68` ya esté
instalado localmente).

### 12.2 Archivos nuevos en esta sesión

- `mlb_kaizen/observability/__init__.py`
- `mlb_kaizen/observability/logging.py`
  - `JsonFormatter`: una línea JSON por log (timestamp, level, module, message
    + campos whitelisted `operation`/`source`/`game_id`/`model_version`/
    `feature_version`).
  - `configure_logging(level=logging.INFO)`: idempotente, reemplaza handlers
    del root logger.
  - `get_logger(name)`.
  - `log_event(logger, message, *, level=, operation=, source=, game_id=,
    model_version=, feature_version=)`: firma cerrada por keyword; no admite
    `**kwargs`, así que no hay forma de loguear un campo arbitrario tipo
    `api_key` sin editar el código fuente. `_reject_sensitive_names` es un
    guard interno adicional, probado directamente en
    `tests/test_logging.py`.
- `tests/test_logging.py` (5 tests)
- `tests/test_domain_models.py` (5 tests: validación de ProbablePitcher,
  LineupSlot, GameLineups)

### 12.3 Archivos modificados en esta sesión

- `mlb_kaizen/data/http.py`: logging ad-hoc reemplazado por `log_event`.
  Importante: los logs de fallo ya NO incluyen la URL completa, solo
  `scheme://host/path` (función `_source_host`), para que un futuro proveedor
  con API key en query string nunca la filtre a un log.
- `mlb_kaizen/interface/cli.py`: `main()` usa `configure_logging()` en vez de
  `logging.basicConfig`. Se agregaron dos subcomandos:
  - `mlb-kaizen probable-pitchers --date YYYY-MM-DD`
  - `mlb-kaizen lineups --game-id mlb:XXX`
  Ninguno de los dos persiste en SQLite todavía (ver 12.5).
- `mlb_kaizen/domain/models.py`: se agregaron `ProbablePitcher`, `LineupSlot`,
  `GameLineups` (dataclasses frozen con validación en `__post_init__`, mismo
  patrón que `Game`/`TeamRunProfile`). Reglas de validación:
  - `ProbablePitcher`: si `status` es `CONFIRMED`/`PROJECTED`, exige
    `pitcher_id` y `pitcher_name`; para cualquier otro status, esos dos campos
    deben estar vacíos (nunca "casi lleno").
  - `GameLineups`: si `status` es `CONFIRMED`/`AVAILABLE`, exige slots en
    ambos equipos; si no, exige que ambos estén vacíos.
- `mlb_kaizen/data/mlb_stats.py`: `MLBStatsProvider` ahora expone:
  - `probable_pitchers_on(date) -> list[ProbablePitcher]` vía
    `schedule?hydrate=probablePitcher` (mismo endpoint que `games_on`, ya
    verificado en vivo en sesiones previas).
  - `lineups_for(game_id) -> GameLineups` vía `/game/{gamePk}/boxscore`,
    parseando el array `team.battingOrder` (orden real de bateo) contra
    `team.players["ID<id>"]` para nombre/posición. Estructura del boxscore
    confirmada por búsqueda web esta sesión (repos comunitarios
    toddrob99/MLB-StatsAPI y axbolduc/gomlb), NO probada contra una respuesta
    en vivo real porque este sandbox no tiene salida de red. **Antes de
    confiar en esto en producción, correr `lineups --game-id` contra un juego
    real con lineup ya publicado y comparar con el boxscore en mlb.com.**
  - Métodos de parseo (`parse_probable_pitchers`, `parse_boxscore_lineups`)
    son `@classmethod`/`@staticmethod` testeables sin red, igual que
    `parse_schedule`.

### 12.4 Investigación de fuentes hecha esta sesión (no todo se integró)

| Fuente | Estado | Nota |
|---|---|---|
| MLB Stats API (pitchers, lineups, stats por jugador) | Verificada y parcialmente integrada | Documentación comunitaria, no oficial-contractual (igual que `games_on`) |
| Clima | Investigada, NO integrada | MLB Stats API trae forecast en el feed del juego; alternativa NWS `api.weather.gov` (oficial, gratis, sin key) por lat/long del venue. Ningún código escrito todavía. |
| Baseball Savant / Statcast | Investigada, BLOQUEADA | CSV descargable sin key, pero no se localizaron términos de uso formales explícitos. Regla 7 del HANDOFF: no integrar sin que el usuario los verifique directamente en baseballsavant.mlb.com. |
| Odds (The Odds API, OddsPapi, SportsGameOdds, RapidOddsAPI, SharpAPI) | Investigada, BLOQUEADA | Información contradictoria entre fuentes sobre límites del free tier de The Odds API. Verificar directamente en la documentación oficial de cada proveedor antes de elegir uno. |

### 12.5 Qué falta — orden recomendado, sin saltos

1. **Persistencia de pitchers/lineups** (Fase 2.2 del HANDOFF original):
   migraciones versionadas de SQLite + tablas `probable_pitchers`,
   `lineups`, y las ya mencionadas de fuentes/errores/versiones de modelo.
   Sin esto, `probable-pitchers`/`lineups` solo sirven para inspección
   manual, no para features reproducibles.
2. **Validar `lineups_for` contra un boxscore real** (ver 12.3) antes de
   construir nada encima.
3. **Clima**: implementar adaptador `api.weather.gov` (gratis, sin key,
   oficial) por lat/long del venue — el `Game.venue_name` ya existe pero no
   hay lat/long todavía; hay que agregarlo al parseo de `games_on` o a un
   adaptador nuevo.
4. **Estadísticas de temporada para features reales**: `people/{id}/stats`
   de MLB Stats API para producir un primer `offensive_index`/
   `run_prevention_index` real por equipo (hoy son valores de ejemplo en
   `docs/analysis-input.md`, nunca usar esos en un análisis real).
5. Solo después: Statcast y odds (bloqueados hasta verificación manual del
   usuario, ver 12.4), backtest walk-forward, calibración.

**No hacer:** ML, señal de apuesta (`POSITIVE_EXPECTED_VALUE`), ni datos
inventados para "completar" el esqueleto. Sigue siendo la regla más
importante del proyecto.

### 12.6 Prompt breve para continuar en otra conversación

> Continúa `MLB KAIZEN`. Lee `HANDOFF.md` completo, incluida la sección 12
> (estado al 2026-09-16), antes de tocar código. Corre
> `python -m unittest discover -s tests -t . -v` primero — debe dar 23/23.
> El siguiente bloque recomendado es 12.5 punto 1 (migraciones SQLite +
> tablas para persistir pitchers/lineups) o punto 2 (validar `lineups_for`
> contra un boxscore real, ya que se implementó sin acceso a red para
> probarlo en vivo). No implementes ML, calibración ni señal de apuesta
> todavía. No agregues Statcast ni un proveedor de odds sin que el usuario
> confirme términos de uso primero.

## 13. Fase 2.2 completada (2026-09-17): migraciones + persistencia de pitchers/lineups

- Nuevo `mlb_kaizen/storage/migrations.py`: lista ordenada de `Migration(version, description, sql)`.
  Migración 1 = esquema original (idéntico, sigue siendo `CREATE ... IF NOT EXISTS`, así que abrir una
  base creada antes de este módulo es seguro). Migración 2 = tablas nuevas `probable_pitcher_snapshots`
  y `lineup_snapshots`.
- `KaizenDatabase.initialise()` ahora aplica migraciones pendientes contra una tabla `schema_migrations`
  (version INTEGER PRIMARY KEY, description, applied_at); es idempotente y segura sobre bases legado
  (probado manualmente: una base con solo `game_snapshots` sin `schema_migrations` se migra sin romperse).
- Se corrigió un hueco real del modelo de dominio: `GameLineups` no tenía `provenance` propia, así que el
  caso NOT_YET_PUBLISHED no registraba cuándo se verificó. Ahora `provenance` es obligatorio en
  `GameLineups` (mismo patrón que `ProbablePitcher`). Esto cambia la firma del constructor —
  `GameLineups(game_id=..., status=..., provenance=..., home_slots=..., away_slots=...)`.
- Nuevos métodos: `store_probable_pitcher`, `probable_pitcher_count`, `store_lineups`,
  `lineup_snapshot_count`.
- `mlb-kaizen probable-pitchers --date` y `mlb-kaizen lineups --game-id` ahora persisten cada registro
  (incluido NOT_YET_PUBLISHED, a propósito) antes de imprimir.
- 3 nuevos tests en `tests/test_database.py` (idempotencia de migraciones, persistencia de pitchers,
  persistencia de lineups confirmados y no publicados) + helpers nuevos en `tests/conftest.py`
  (`probable_pitcher`, `confirmed_lineups`, `not_yet_published_lineups`). Suite completa: 26/26 verde.

Siguiente bloque recomendado: validar `lineups_for` contra un boxscore real (sigue sin probarse contra
red viva — ver sección 12.3), luego adaptador de clima o estadísticas de temporada para features reales.

## 14. Validación contra red real completada (2026-09-17)

Se confirmó `lineups_for`/`parse_boxscore_lineups` contra una respuesta real de
`statsapi.mlb.com/api/v1/game/{gamePk}/boxscore` (fetch en vivo, no simulado). La
estructura asumida sin haber podido probarla era correcta: `team.battingOrder` es un
array de IDs de jugador en orden 1-9, verificado cruzando contra el campo individual
`battingOrder` ("100".."900") de cada jugador en `team.players`. Se agregó
`test_boxscore_lineups_matches_verified_live_response_shape` en `tests/test_mlb_stats.py`
como fixture de regresión con datos reales (gamePk 529572, lineup visitante completo).
No se necesitó ningún cambio de código — el parser ya estaba bien. Suite completa: 27/27.

Siguiente bloque recomendado: adaptador de clima (api.weather.gov) o estadísticas de
temporada para offensive_index/run_prevention_index reales (ver sección 12.5, puntos 3-4).

## 15. Clima y estadísticas de temporada (2026-09-17)

Se completaron dos bloques en paralelo (ya había avance parcial de modelos de dominio
de un corte de contexto anterior en la misma sesión):

- **VenueLocation / GameWeather** (`mlb_kaizen/domain/models.py`): coordenadas fijas de
  un venue y un pronóstico point-in-time o su ausencia registrada. `GameWeather.status`
  AVAILABLE exige al menos una lectura; cualquier otro estado prohíbe llevar campos de
  pronóstico (mismo patrón que ProbablePitcher/GameLineups).
- **TeamSeasonStats**: agregados crudos de temporada (AVG/OBP/SLG/runs_scored,
  ERA/WHIP/earned_runs/innings_pitched), deliberadamente SIN offensive_index ni
  run_prevention_index — normalizarlos contra el promedio de liga es Fase 4
  (feature store), no este bloque.
- `mlb_kaizen/data/mlb_stats.py`: `venue_location(venue_id)` vía
  `/v1/venues/{id}?hydrate=location` (defaultCoordinates.{latitude,longitude}) —
  **verificado en vivo** (Dodger Stadium, venueId 22) el 2026-09-17.
  `team_season_stats(team_id, team_name, season)` combina `/v1/stats?group=hitting` y
  `group=pitching` — ruta y query params confirmados contra el código fuente oficial de
  toddrob99/MLB-StatsAPI (endpoints.py); nombres de campo (`runs`, `gamesPlayed`, `era`)
  corroborados contra el boxscore real ya verificado en la sección 14. **No se pudo hacer
  un fetch en vivo del endpoint completo `/v1/stats` de temporada en esta sesión** — antes
  de confiar en `team-stats` para producción, correrlo una vez contra un equipo real y
  comparar campos.
- `mlb_kaizen/data/weather.py` (nuevo): `NWSWeatherProvider.forecast_for(game_id, venue,
  target_time)` usa `api.weather.gov` (oficial, gratis, sin key) en dos pasos:
  `/points/{lat},{lon}` → URL de forecast → periodo que cubre `target_time`. Estructura
  confirmada contra documentación oficial NWS y un ejemplo de terceros con request/response
  reales, pero **no se hizo un fetch en vivo end-to-end de api.weather.gov en esta sesión**
  (el motor de búsqueda no devolvió una URL fetchable de /points para una coordenada
  específica). Cobertura solo EE.UU.: un venue fuera de cobertura (ej. Toronto) debe
  resolver a NOT_AVAILABLE, nunca a un dato inventado — ya cubierto por el manejo de
  errores del proveedor.
- Migración 3 (`mlb_kaizen/storage/migrations.py`): tablas `weather_snapshots` y
  `team_season_stat_snapshots`, mismo patrón append-only que las anteriores.
  `store_weather`/`weather_snapshot_count`, `store_team_season_stats`/
  `team_season_stat_count` en `KaizenDatabase`.
- CLI: `mlb-kaizen team-stats --team-id --team-name --season`,
  `mlb-kaizen weather --game-id --venue-id --at ISO8601`. Ambos persisten antes de
  imprimir.
- 13 tests nuevos (parseo de venue y team-stats con fixtures reales, selección de periodo
  de clima, validación de dominio VenueLocation/GameWeather, persistencia de ambas tablas
  nuevas). Suite completa: 40/40 verde.

Siguiente bloque recomendado, en orden:
1. Verificar en vivo `team-stats` y `weather` contra datos reales (ver arriba) antes de
   confiar en ellos para producción.
2. Fase 4 (feature store): documentar la fórmula que convierte TeamSeasonStats + promedio
   de liga en TeamRunProfile.offensive_index/run_prevention_index, con ficha por feature
   (fuente, disponibilidad temporal, missing-value policy) como pide el HANDOFF original.
3. Wirear `weather` a `--game-id` real (hoy requiere `--venue-id` y `--at` por separado;
   falta la capa que resuelva venue+hora de inicio desde un game_snapshot guardado).

## 16. Intento de verificación en vivo de team-stats y weather (2026-09-17)

Se intentó repetidamente hacer fetch en vivo de `statsapi.mlb.com/api/v1/stats` (team
season stats) y `api.weather.gov/points/{lat},{lon}`, sin éxito: la herramienta de fetch
de esta sesión solo permite abrir URLs que aparecen como enlace de un resultado de
búsqueda, y ninguna búsqueda logró indexar la URL cruda de estos dos endpoints JSON
(sí funcionó para `venues` y `boxscore` en sesiones anteriores porque esas URLs sí
aparecieron como enlaces).

En su lugar se corroboró la forma exacta de ambas respuestas contra **ejemplos reales
documentados por terceros**, no contra un fetch propio de esta sesión:
- `api.weather.gov/points`: ejemplo real citado en la documentación oficial NWS de
  gridpoints (weather-gov.github.io/api/gridpoints) y en una discusión de GitHub del repo
  oficial `weather-gov/api` — confirma `properties.forecast`, `properties.gridId`, etc.
  Se agregó `test_extract_forecast_url_matches_documented_points_response_shape` en
  `tests/test_weather.py`.
- `statsapi.mlb.com/v1/stats`: dump real de atributos impreso en el README de
  `python-mlb-statsapi` (pypi.org/project/python-mlb-statsapi) — confirma los nombres de
  campo `gamesPlayed`, `runs`, `avg`, `obp`, `slg`, `era`, `whip`, `earnedRuns`. Se anotó
  esto en el docstring de `test_team_season_stats_combines_hitting_and_pitching_splits`.

No se cambió código — solo se documentó honestamente el nivel de confianza real. **Sigue
pendiente una verificación en vivo genuina**: correr `mlb-kaizen team-stats --team-id 147
--team-name "New York Yankees" --season 2026` y `mlb-kaizen weather --game-id mlb:X
--venue-id 22 --at <ISO>` una vez con red real disponible (esta sesión de desarrollo no
tiene salida de red en el entorno de ejecución, solo en las herramientas de búsqueda/fetch
web, que a su vez tienen esta limitación de indexado para URLs de API cruda). Suite
completa: 41/41 verde.

## 17. Fase 4 (feature store) — primera ficha implementada (2026-09-17)

Se corrigió un hueco encontrado al construir esto: `TeamSeasonStats` solo guardaba
`earned_runs` (carreras limpias), no `runs_allowed` (carreras totales permitidas, campo
`runs` del grupo `pitching`). `run_prevention_index` necesita el total, no solo las
limpias, o subestimaría sistemáticamente cuánto permite anotar un equipo. Se agregó el
campo `runs_allowed` a `TeamSeasonStats` con una validación de integridad
(`runs_allowed >= earned_runs`).

Nuevo módulo `mlb_kaizen/features/run_profile.py`: `compute_team_run_profile(stats,
league_average_runs_per_game, games_for_full_confidence=30) -> TeamRunProfile`.

- Fórmula: `offensive_index = (runs_scored/games_played) / league_avg`,
  `run_prevention_index = (runs_allowed/games_played) / league_avg`.
- **No calcula ni fetchea el promedio de liga** — es un parámetro obligatorio de quien
  llama. Calcular uno real requiere agregar las 30 franquicias, que sigue bloqueado por la
  misma limitación de fetch en vivo de la sección 16.
- `data_quality = min(1.0, games_played / 30)` — alimenta directamente la `QualityGate`
  existente en `validation/quality.py`.
- La `provenance` del perfil resultante hereda `retrieved_at` del `TeamSeasonStats` de
  origen, NO la hora en que se corrió el cómputo — para que un backtest pueda verificar
  disponibilidad temporal correctamente aunque el cálculo se corra días después.
- `games_played == 0` o `league_average_runs_per_game <= 0` → `ValueError` explícito,
  nunca un perfil con índices en 1.0 disfrazado de "promedio".
- Versionado: constante `FORMULA_VERSION = "run_profile_formula_v1"`, guardada en
  `provenance.source_version`. Cambiar la fórmula exige incrementarla.

Ficha completa (fuente, disponibilidad temporal, fórmula, política de valores faltantes,
versionado, pendientes) en `docs/features/run_profile.md`, como exige el HANDOFF original
para Fase 4.

8 tests nuevos en `tests/test_run_profile.py`. Suite completa: 47/47 verde.

Siguiente bloque recomendado: resolver el cálculo real de `league_average_runs_per_game`
(agregado de las 30 franquicias) para poder usar `compute_team_run_profile` sin depender
de un número pasado a mano — o, si se prefiere seguir el orden original del HANDOFF,
avanzar a Fase 5 (baseline entrenable) usando por ahora `league_average_runs_per_game`
como parámetro explícito documentado.

## 18. Fase 4 — league_average_runs_per_game resuelto (2026-09-17)

Se resolvió el bloqueo principal de Fase 4: `MLBStatsProvider.league_average_runs_per_game(season)`
suma `runs` y `gamesPlayed` de las 30 franquicias en una sola llamada
(`/v1/stats?stats=season&group=hitting&sportId=1&season=Y&limit=30`, sin `teamId`), en vez de asumir
una constante. `parse_league_average_runs_per_game` falla explícito (`ValueError`) si:
- hay menos de `minimum_expected_teams=28` splits (respuesta claramente truncada — el umbral es 28,
  no exactamente 30, para no romper el día que MLB expanda la liga);
- hay un `team.id` duplicado (la forma de la respuesta no sería una fila por equipo);
- falta `runs` o `gamesPlayed` en algún split.

`mlb_kaizen/features/run_profile.py` no cambió su fórmula ni su diseño — sigue sin fetchear nada, el
promedio de liga se le sigue pasando como parámetro explícito (mantiene el módulo testeable sin red y
reutilizable si el promedio viniera de otra fuente, como un snapshot histórico para backtest).

Nuevo comando CLI `mlb-kaizen run-profile --team-id --team-name --season` que une
`team_season_stats` + `league_average_runs_per_game` + `compute_team_run_profile` y persiste el
`TeamSeasonStats` crudo (el `TeamRunProfile` derivado no tiene tabla propia todavía — sigue siendo
efímero, calculado bajo demanda). Probado sin red: falla explícito con `DATA NOT VERIFIED`, nunca
imprime un índice inventado.

**Sigue pendiente la misma limitación de la sección 16**: no se pudo hacer un fetch en vivo genuino del
endpoint `/v1/stats` sin `teamId` en esta sesión (misma restricción de indexado del buscador). La lógica
de suma/validación está cubierta por 3 tests nuevos con fixtures sintéticas de 30 equipos, pero **antes
de confiar en `run-profile` para producción, correrlo una vez con red real disponible**.

3 tests nuevos en `tests/test_mlb_stats.py`. Suite completa: 50/50 verde.

**Fase 4 se considera funcionalmente cerrada**: existe la ficha documentada
(`docs/features/run_profile.md`), la fórmula, el cálculo real del promedio de liga, y un comando CLI
que ejecuta el ciclo completo. Queda como deuda técnica menor la verificación en vivo pendiente
(sección 16 + esta sección) y decidir si `TeamRunProfile` necesita su propia tabla de persistencia
antes de Fase 5.

## 19. Auditoría de trabajo externo (2026-09-18)

El usuario trajo de vuelta el repo tras trabajarlo en otra sesión/herramienta (con acceso
a red real), acompañado de un resumen que afirmaba "8/8 fases, 67/67 tests, ANALYST MODE
DONE". Siguiendo la misma regla que ha gobernado todo el proyecto (código y tests mandan,
no los resúmenes), se auditó el zip antes de aceptar nada:

- **Discrepancia real encontrada**: la suite tal cual llegó daba 67 tests con 2 errores en
  este entorno (`jsonschema` no está instalado ni se puede instalar sin red aquí). No era
  deshonestidad — la dependencia está correctamente declarada como opcional en
  `pyproject.toml` — pero los tests fallaban en vez de saltarse limpio. **Corregido**:
  `tests/test_schema.py` ahora usa `@unittest.skipUnless(HAS_JSONSCHEMA, ...)`. Suite final:
  67/67 con 2 *skipped* honestos (no silenciados, no fallidos).
- **Revisión de rigor en los módulos de más riesgo** (Analyst Mode, walk-forward,
  calibración, ML challenger, adaptador de odds): sin datos inventados, sin afirmaciones de
  validación sin evidencia. Específicamente:
  - `ModelValidationStatus.VALIDATED` solo se produce si `calibrated=True` se pasa
    explícitamente — nada en el camino real de Analyst Mode lo activa; siempre queda
    `EXPERIMENTAL`.
  - `MachinePick.status` siempre es `"preliminary"`, nunca se presenta como señal
    confirmada.
  - `walk_forward_evaluate` entrena solo con filas anteriores (`train = ordered[:start]`) y
    evalúa solo en las posteriores — sin fuga temporal.
  - `temporal_calibration_report` calibra en el primer bloque cronológico y evalúa en el
    segundo — mismo principio.
  - El adaptador de SportsGameOdds envía la API key por header (`x-api-key`), nunca en la
    URL; `CachedHttpClient` nunca persiste headers al caché.
  - `STATUS.md` distingue explícitamente "engineering status" (código existe y probado) de
    "evidence status" (validación empírica real) — Fases 5-7 quedan marcadas
    `REAL HISTORICAL DATA PENDING`, no como validadas.
  - Sin lenguaje prohibido (`SAFE BET`/`GUARANTEED`/`LOCK`) en los reportes.
- **Gap menor detectado, no corregido todavía**: `CalculationStatus.BLOCKED` existe como
  valor del enum pero `QualityGate.assess` siempre devuelve `CalculationStatus.READY` — no
  hay ningún camino que lo active. Es defendible en la arquitectura actual (el modelo base
  no depende todavía de pitcher/lineup/odds, así que el cálculo nunca queda
  matemáticamente bloqueado por su ausencia), pero es una pieza de la visión del
  documento AGENT MASTER CONTROLLER que quedó como código muerto, no como mentira. Revisar
  cuando el modelo empiece a depender de esos inputs.
- Se adoptó este repo como la copia de trabajo canónica de la sesión (reemplazó la copia
  local previa, que quedó estrictamente atrás en historial de git).

Commits del trabajo externo, verificados con git log continuo desde `307411b`:
`a27640c` (feat: complete analyst and evaluation pipeline), `5cd4593` (checkpoint), y el
fix de esta auditoría: `a293769`.

## 20. Herramienta real de construcción de dataset histórico point-in-time (2026-09-18)

El usuario pidió juntar 40-50 partidos reales para validar el modelo. Se descubrió una
limitación real de la herramienta de fetch web de esta sesión: no hace fetches arbitrarios
en vivo, sino que responde contra un índice/caché de páginas ya vistas, y a veces normaliza
silenciosamente una fecha pedida a otra distinta ya indexada (se pidió
`startDate=2025-07-15` y devolvió el calendario de `2026-08-14` sin avisar). Esto hace
imposible encadenar múltiples fechas específicas a demanda desde este entorno. Sí se
consiguió un día completo real y verificado: 15 partidos del 4 de julio de 2025 con
marcador final (`schedule?startDate=2025-07-04&endDate=2025-07-04&hydrate=team,linescore`).

En vez de forzar más fetches poco fiables, se construyó la herramienta correcta para que se
corra donde sí haya red real (Claude Code, máquina local, otra sesión):

- **`CompletedGameResult`** (`mlb_kaizen/domain/models.py`): identidad + marcador final de
  un partido, distinto de `Game` (que es pre-partido, sin marcador) a propósito.
- **`MLBStatsProvider.completed_games(start_date, end_date)`** + `parse_completed_games`:
  una sola llamada con `startDate`/`endDate`/`hydrate=team,linescore` (verificado en vivo
  hoy) en vez de un loop por fecha — sigue la regla de batch del proyecto. Filtra a solo
  `status.detailedState == "Final"`; un partido "Final" sin score publicado (raro pero
  observado en la API cruda) se descarta explícitamente en vez de inventar un 0-0.
- **`mlb_kaizen/training/build_dataset.py`** (nuevo, puro, sin red):
  `build_point_in_time_rows(games, minimum_prior_games=1, minimum_league_games_for_average=10,
  home_advantage=1.035)`. Acumula carreras anotadas/permitidas por equipo y el total de
  liga **en orden cronológico**, actualizando los acumuladores *después* de usarlos para
  cada fila — así el resultado de un partido nunca se filtra a sus propias features
  (probado explícitamente: `test_a_games_own_result_never_appears_in_its_own_features`).
  El promedio de liga usado en cada fila también es point-in-time (solo partidos
  estrictamente anteriores), no un promedio de toda la ventana — evita fuga de información
  futura hacia filas tempranas (`test_league_average_is_point_in_time_not_whole_window`).
  Reutiliza `run_rate_index` (extraído de `features/run_profile.py` en un refactor menor)
  como única fuente de verdad de la fórmula, para que ambos caminos nunca diverjan.
- Se encontró y corrigió un bug real antes de que se manifestara: `feature_timestamp` no
  puede ser "ahora" (`datetime.now()`), porque `HistoricalGameRow` exige
  `feature_timestamp <= prediction_timestamp`, y la hora actual siempre es posterior a un
  partido histórico. Se usa `game.start_time` (documentado en el código: es la cota
  correcta y honesta ya que la acumulación garantiza que todo insumo viene de partidos
  estrictamente anteriores).
- **`scripts/build_historical_dataset.py`**: CLI que hace el fetch real + llama al motor
  puro + guarda JSONL compatible con `training/dataset.py` (`load_jsonl`/`save_jsonl` ya
  existentes) + imprime cobertura (partidos traídos, filas usables, partidos saltados por
  historial insuficiente). Probado sin red en esta sesión: falla limpio con
  `DATA NOT VERIFIED`, nunca escribe un dataset inventado.

8 tests nuevos (`tests/test_build_dataset.py`, más 2 en `tests/test_mlb_stats.py` con
fixture real del 4 de julio de 2025). Suite completa: 75/75 verde (2 *skipped* por
`jsonschema`, igual que antes).

**Siguiente paso real**: correr
`python3 scripts/build_historical_dataset.py --start-date <inicio> --end-date <fin>
--output data/historical/<nombre>.jsonl` en un entorno con red real (varias semanas de
rango para que el umbral de historial mínimo produzca filas), y luego alimentar ese JSONL a
`mlb_kaizen.evaluation.walk_forward.walk_forward_evaluate` para obtener MAE/RMSE/Brier
reales — ver sección 19 sobre qué ya existe del lado de evaluación.

## 21. Auditoría del dataset externo de Colab (2026-09-19)

El usuario trajo `mlb_kaizen_dataset.zip`, generado por un collector Python propio corrido
en Google Colab (con red real) contra `statsapi.mlb.com/api/v1/schedule`
(`hydrate=team,linescore,probablePitcher`, `gameType=R`). Se auditó de forma independiente
antes de usarlo (misma regla del proyecto: nunca confiar en un resumen sin verificar):

- **12,045 partidos únicos** (2022-2026), 0 duplicados en el archivo normalizado
  (confirmado independientemente, coincide con "duplicates_removed: 195" del propio reporte
  del collector — esos 195 ya se habían quitado antes de escribir el archivo final).
- 2430 partidos por temporada completa (2022-2025) = exactamente 30 equipos × 162 juegos / 2
  — cuadra perfecto con un calendario real completo, buena señal de cobertura.
- 2026 (parcial, hasta el 19-sep): 2325 partidos.
- 12030 `Final`, 15 `Preview`. De los `Final`, 179 sin score publicado (coincide exacto con
  "194 sin score" del reporte del collector una vez se suman los 15 `Preview`).
- Esquema consistente en los 5 archivos (`schema_version: "1.0"`), con `game_id`, equipos,
  score, `probable_pitchers`, venue, y metadata de colección (`retrieved_at`,
  `request_url`, `raw_sha256`) — suficiente para persistencia con provenance real.

**Veredicto: dataset genuinamente real y utilizable.** No se detectó ninguna discrepancia
real entre lo auditado y lo que el collector reportó de sí mismo.

## 22. Ingesta real + primera evaluación con evidencia real (2026-09-19)

Se construyó el puente entre este dataset externo y el pipeline ya existente:

- `mlb_kaizen/training/external_collector.py`: loader del formato normalizado del
  collector (distinto del formato que produce `MLBStatsProvider.parse_completed_games` —
  cada uno lee una fuente distinta, mantenidos separados a propósito). Excluye
  silenciosamente `Preview` y `Final` sin score (mismo criterio que el proveedor propio);
  falla loud ante `schema_version` inesperada o campos faltantes.
- `scripts/ingest_external_collector.py`: une el loader con `build_point_in_time_rows` (ya
  existente, sección 20) y guarda el JSONL final.
- Datos copiados dentro del repo en `data/external/mlb_kaizen_colab_2026-09-19/`
  (`normalized/` + `audit/`, 11 MB — el `raw/` de 73 MB se dejó fuera del repo por tamaño,
  el usuario lo conserva aparte si hace falta reprocesar).
- **Corrida real**: 11,851 partidos cargados → **11,836 filas point-in-time reales**
  escritas en `data/historical/2022_2026_point_in_time.jsonl` (solo 15 partidos saltados
  por historial insuficiente al inicio de 2022).
- **Primera evaluación walk-forward con datos reales** (fold único, filas 8000-11836):

  | Modelo | Brier | Log loss |
  |---|---|---|
  | Referencia ingenua (tasa de victoria local histórica) | 0.2490 | 0.6912 |
  | Baseline Poisson | 0.2494 | 0.6919 |
  | Random Forest challenger | 0.2542 | 0.7026 |

  **Ninguno de los dos modelos supera de forma clara a la referencia ingenua.** Detalle
  completo, MAE de carreras, e interpretación honesta en
  `data/evaluation/first_real_evaluation_2026-09-19.md`. Esto no invalida el pipeline (que
  corrió de punta a punta, sin fuga temporal, sobre datos reales) — dice que las features
  actuales (solo carreras anotadas/permitidas acumuladas, sin pitcher, sin bullpen, sin
  parque, sin ajuste por rival) todavía no aportan ventaja predictiva medible. Es
  exactamente el tipo de evidencia que la sección 56 del proyecto pide antes de afirmar
  cualquier ventaja — y la respuesta honesta hoy es: todavía no hay ventaja demostrada.

8 tests nuevos (`tests/test_external_collector.py`, con fixtures reales extraídas
literalmente del dataset). Suite completa: 81/81 (2 *skipped* por `jsonschema`, igual que
antes).

**Siguiente paso de mayor impacto** (no el más fácil, el de mayor impacto esperado, según
la sección 22 del documento maestro): usar `probable_pitchers`, ya presente en el dataset
pero sin usar todavía, para ajustar el modelo por fuerza del abridor. Ver
`data/evaluation/first_real_evaluation_2026-09-19.md` para el resto de la lista priorizada.

## 23. Puente del modelo entrenado al comando de análisis (2026-10-03)

Tras recuperar y validar E2--E5, corregir la regularización de E3 y evaluar la
calibración temporal, se conectó el modelo Poisson E3 entrenado con Analyst
Mode. El comando `analyze` acepta ahora:

- `--trained-model RUTA`: artefacto Poisson local y confiable creado por
  `train-model`.
- `--calibrator RUTA`: calibrador Platt local opcional; requiere el modelo
  entrenado y rechaza cualquier otro tipo de artefacto.

Sin estas opciones, se conserva la fórmula fija anterior como alternativa.
El sistema no cambia su declaración de seguridad: aun usando el modelo E3 y el
calibrador, cada resultado sigue marcado como `EXPERIMENTAL`, porque la mejora
fuera de muestra fue pequeña y todavía no equivale a validación de producción.

Verificación: 120/120 tests. Próxima acción: hacer reproducible la creación del
artefacto de calibración desde el flujo de línea de comandos y decidir, con esa
base operativa, si iniciar el experimento de lineups (E6).

## 24. Auditoría pre-E6 (2026-10-03)

Se reconstruyó E0--E5 sin cambiar código de modelo ni correr E6. E3 sigue
siendo la única mejora demostrada: reducir `alpha` de 1.0 a 0.0001, elegido
con 2022--2024/2025 sin tocar 2026, llevó Brier a 0.2463 frente a 0.2491 de la
referencia ingenua. E2 (abridor), E4 (parque) y E5 (bullpen) no añadieron una
mejora incremental demostrable.

El diagnóstico muestra que bullpen y parque están parcialmente absorbidos por
la prevención de equipo (correlaciones aproximadas 0.87--0.88 y 0.70);
abridor tiene solapamiento moderado (0.38), por lo que queda abierta la
limitación de representación lineal. E3 discrimina modestamente (55.09% de
accuracy vs 53.11% de siempre elegir local), pero su media de probabilidad local
(50.43%) sigue bajo la tasa observada (53.11%). Platt mejora Brier sólo de
0.2463 a 0.2462.

**Decisión: READY_FOR_E6** únicamente para auditar disponibilidad histórica
point-in-time de lineups. No equivale a modelo validado ni rentable. Registro
completo: `docs/experiments/2026-10-03-pre-e6-audit.md`.
