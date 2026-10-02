# Handoff — MLB KAIZEN

> Recovery note (2026-10-01): this document describes the supplied foundation archive. A separate historical note reports later E2–E5 work and 94/94 passing tests, but that code is not present in this checkout. Read `STATUS.md` and `.agent/checkpoint.json` before relying on the state below.

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

