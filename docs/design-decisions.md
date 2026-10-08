# design-decisions.md

Decisiones con `Status: LOCKED` no se vuelven a debatir sin una tarea
explícita que las reabra.

## DD-015 — Regularización Poisson seleccionada sin tocar la temporada de prueba

La configuración por defecto usa `alpha=0.0001`, elegida con 2022–2024 para
entrenar y 2025 para validar. La temporada 2026 se mantuvo fuera de esa
decisión y se usó una sola vez para comprobarla. Esto sustituyó `alpha=1.0`,
que comprimía casi por completo la información de equipo. No convierte al
modelo en validado para producción: es una mejora reproducida en una sola
temporada fuera de muestra.

---

## DD-016 — La inferencia calibrada se distribuye como una pareja inseparable

El modelo Poisson E3+E7+E8 y el calibrador Platt E11 se guardan y cargan como
un solo contrato de inferencia versionado. El contrato conserva el orden exacto
de sus 13 features, el esquema, el experimento, las versiones de modelo y
preprocesamiento, y los metadatos temporales de entrenamiento. La ruta de
predicción nunca reentrena ni completa features por defecto: rechaza de forma
explícita entradas, orden o metadatos incompatibles.

**Razón:** un calibrador ajustado para otro modelo o para otro orden de
features puede devolver una probabilidad aparentemente válida, pero equivocada.
Hacer fallar ese caso es más seguro y reproducible que reconstruirlo de forma
silenciosa.

**Status:** LOCKED

---

## DD-017 — Un vector diario sólo representa evidencia disponible antes del partido

Cada vector E3+E7+E8 diario se persiste append-only junto con el instante de
predicción y el último `retrieved_at` de sus fuentes. El sistema rechaza
resultados obtenidos después de ese instante, el resultado del propio juego y
predicciones hechas al inicio o después de éste.

**Razón:** recalcular una feature histórica hoy puede producir números
plausibles, pero no demuestra que fueran conocidos entonces. La captura
operativa debe preservar tanto los valores como su disponibilidad temporal.

**Status:** LOCKED

---

## DD-018 — El modelo regular no emite predicciones de playoffs

`daily-e11-inference` exige que MLB identifique el juego como `game_type: R`.
Los códigos de playoffs y un tipo ausente se rechazan hasta que un experimento
postseason separado tenga dataset, evaluación temporal y artefacto propios.

**Razón:** una predicción de playoffs puede parecer numéricamente válida, pero
no es evidencia comparable con un modelo entrenado y calibrado sólo en
temporada regular. Bloquearla es más honesto que etiquetarla como equivalente.

**Status:** LOCKED

---

## DD-019 — Resultados históricos oficiales se archivan separados de las features

La colección E12 guarda cada resultado final oficial con `game_type`, marcador,
hora de inicio y procedencia en un JSONL versionado. El `retrieved_at` acredita
cuándo se descargó el resultado, no que el resultado fuera conocido antes del
partido. El archivo no se sobrescribe; los constructores de features deben
seguir usando sólo partidos estrictamente anteriores al que se predice.

**Razón:** separar el archivo de resultados de un dataset de entrenamiento
evita confundir datos retrospectivos legítimos con evidencia pregame, y permite
auditar la separación entre temporada regular y playoffs antes de E12.

**Status:** LOCKED

---

## DD-020 — Las cuotas manuales son observaciones fechadas, no precios inferidos

`record-market-quote` requiere un `observed_at` con zona horaria y agrega cada
captura a `market_quotes` sin modificar registros previos. El timestamp acredita
cuándo el usuario vio el precio; no lo llama apertura ni cierre sin evidencia
temporal adicional. El precio americano original se conserva junto con su
equivalente decimal.

**Razón:** CLV y movimiento de mercado no se pueden reconstruir si una línea
posterior reemplaza la anterior o si se confunde la hora de captura con una
etiqueta de apertura/cierre. Una cuota observada tampoco es una predicción ni
una recomendación.

**Status:** LOCKED

---

## DD-021 — El Control Center de Colab separa código efímero y datos persistentes

El notebook visual obtiene el código desde GitHub en cada sesión de Colab y
guarda base SQLite, caché y artefactos locales bajo `MyDrive/MLB_KAIZEN/`. La
interfaz usa los mismos contratos de calendario, cuotas, resultados e
inferencia del paquete; no mantiene una segunda lógica paralela en el
notebook.

**Razón:** la máquina de Colab puede desaparecer al cerrar o expirar la sesión.
Separar el código versionado de los datos del usuario permite actualizar el
Control Center sin perder capturas históricas, a la vez que conserva un flujo
visual para quien no usa PowerShell.

**Status:** LOCKED

---

**ID:** DD-001
**Decisión:** Todo registro que puede representar una ausencia de dato
(`ProbablePitcher`, `GameLineups`, `GameWeather`) lleva `provenance`
obligatoria incluso en su estado "no disponible" (`NOT_YET_PUBLISHED`,
`NOT_AVAILABLE`).
**Razón:** Saber *cuándo* se verificó la ausencia es tan importante como el
dato mismo para reconstrucción point-in-time en un backtest futuro. Sin esto,
"lo comprobamos y no estaba" es indistinguible de "nunca lo comprobamos".
**Alternativas consideradas:** `provenance` opcional solo en el estado
disponible — descartado, perdía la garantía de auditoría temporal.
**Status:** LOCKED

---

**ID:** DD-002
**Decisión:** `run_prevention_index` usa `runs_allowed` (carreras totales
permitidas) del grupo `pitching`, no `earned_runs`.
**Razón:** `earned_runs` excluye carreras por error; usar solo carreras
limpias subestima sistemáticamente cuánto permite anotar un equipo.
**Alternativas consideradas:** usar `earned_runs` por ser más "limpio"
estadísticamente — descartado porque el modelo necesita carreras reales
cruzando el plato, no una métrica de habilidad del pitcher aislada del
fielding.
**Status:** LOCKED

---

**ID:** DD-003
**Decisión:** `compute_team_run_profile` recibe `league_average_runs_per_game`
como parámetro obligatorio; el módulo `features/run_profile.py` nunca
fetchea nada.
**Razón:** Mantiene la fórmula pura y testeable sin red, y reutilizable si el
promedio de liga viene de otra fuente (ej. un snapshot histórico congelado
para backtest en vez de un fetch en vivo).
**Alternativas consideradas:** que la función acepte un `MLBStatsProvider` e
internamente resuelva el promedio — descartado, acoplaría la fórmula a un
proveedor concreto y complicaría el testing.
**Status:** LOCKED

---

**ID:** DD-004
**Decisión:** La `provenance` de una feature derivada (ej. `TeamRunProfile`)
hereda `retrieved_at` de los datos crudos de origen, nunca la hora en que se
ejecutó el cómputo.
**Razón:** Un cómputo puede correr días después de obtener los datos crudos;
usar `now()` daría una falsa sensación de frescura y rompería la
verificación de disponibilidad temporal en un backtest.
**Alternativas consideradas:** guardar ambos timestamps (cómputo + dato
origen) — pospuesto; `DataProvenance` solo tiene un campo `retrieved_at`,
revisar si Fase 5/6 necesitan el segundo timestamp.
**Status:** LOCKED (revisar si Fase 5/6 lo requieren)

---

**ID:** DD-005
**Decisión:** No implementar un flag `--force` genérico que desactive toda
validación. Usar modos explícitos y auditables (`live`/`snapshot`/`manual`/
`hybrid`) cuando se necesite saltarse una fuente automática.
**Razón:** Un bypass universal oculta *qué* validación se saltó y *por qué*;
un modo explícito deja rastro de qué se hizo y con qué input.
**Alternativas consideradas:** ninguna — regla adoptada directamente del
documento AGENT MASTER CONTROLLER del usuario.
**Status:** LOCKED

---

**ID:** DD-006
**Decisión:** Las migraciones de SQLite son aditivas y versionadas
(`schema_migrations`), nunca se reescribe una migración ya aplicada.
Migración 1 replica el esquema original con `CREATE TABLE IF NOT EXISTS`
para que una base creada antes de este sistema se pueda abrir sin romperse.
**Razón:** Permite abrir bases de datos legado sin migración manual, y deja
un registro auditable de qué versión de esquema tiene cada base.
**Alternativas consideradas:** un solo script `initialise()` idempotente sin
versionado — era el diseño original de Fase 1; se reemplazó al necesitar
tablas nuevas sin arriesgar las existentes.
**Status:** LOCKED

---

**ID:** DD-007
**Decisión:** El agregado de promedio de liga (`league_average_runs_per_game`)
exige al menos `minimum_expected_teams=28` splits distintos en la respuesta,
no exactamente 30.
**Razón:** Falla loud ante una respuesta claramente truncada (ej. filtro de
season mal aplicado) sin romper el día que MLB expanda la liga a más de 30
equipos.
**Alternativas consideradas:** exigir exactamente 30 — descartado por
fragilidad ante expansión futura de la liga.
**Status:** LOCKED

---

**ID:** DD-008
**Decisión:** El logging estructurado (`log_event`) nunca registra una URL
completa con query string, solo `scheme://host/path`; y su firma es cerrada
por keyword (sin `**kwargs`) para que no se pueda colar un campo con nombre
tipo credencial.
**Razón:** Una URL de un futuro proveedor con licencia (odds) podría llevar
una API key en el query string — el logging no debe poder filtrarla ni por
descuido.
**Alternativas consideradas:** lista negra de nombres de campo sensibles
aplicada solo en tiempo de ejecución sobre `**kwargs` — se mantiene como
segunda capa de defensa (`_reject_sensitive_names`), pero la firma cerrada es
la garantía principal.
**Status:** LOCKED

---

**ID:** DD-009
**Decisión:** `MODEL_UNCALIBRATED` no bloquea el cálculo de Analyst Mode. Cálculo, calidad de datos y validación del modelo son estados independientes.
**Razón:** El usuario necesita ver la simulación experimental antes de terminar el backtest. Ocultar números no mejora su trazabilidad; etiquetarlos correctamente sí.
**Status:** LOCKED

---

**ID:** DD-010
**Decisión:** Los análisis aceptan modos explícitos `LIVE`, `SNAPSHOT`, `MANUAL` y `HYBRID`.
**Razón:** El mercado puede conocer un pitcher antes de que un proveedor haya publicado la confirmación. El sistema debe permitir el input humano sin fingir que fue verificado por el proveedor.
**Status:** LOCKED

---

**ID:** DD-011
**Decisión:** No usar un valor mágico por defecto para `league_runs_per_team` en el baseline.
**Razón:** Un promedio fijo no debe disfrazarse como dato vigente ni histórico. El valor debe venir de un snapshot o de un input explícito.
**Status:** LOCKED

---

**ID:** DD-012
**Decisión:** `machine_pick` es una salida `preliminary` mientras la validación temporal no esté completada.
**Razón:** Una diferencia entre probabilidad de modelo y mercado es una salida matemática, no evidencia automática de rentabilidad futura.
**Status:** LOCKED

---

**ID:** DD-013
**Decisión:** Todo dataset de entrenamiento/backtest debe imponer `feature_timestamp <= prediction_timestamp`.
**Razón:** Esta es la barrera mínima contra información del futuro en las features históricas.
**Status:** LOCKED

---

**ID:** DD-014
**Decisión:** Los secretos de proveedores se envían mediante headers y nunca como query parameters cuando el cliente HTTP lo soporta.
**Razón:** El cliente de caché puede persistir la URL; usar `x-api-key` evita que una API key quede almacenada accidentalmente en un snapshot de caché.
**Status:** LOCKED
