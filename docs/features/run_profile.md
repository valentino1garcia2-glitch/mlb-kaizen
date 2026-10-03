# Feature: offensive_index / run_prevention_index

Implementación: `mlb_kaizen.features.run_profile.compute_team_run_profile`
Versión de fórmula: `run_profile_formula_v1` (constante `FORMULA_VERSION`)

## Fuente

- `mlb_kaizen.domain.models.TeamSeasonStats`, producido por
  `MLBStatsProvider.team_season_stats(team_id, team_name, season)` vía
  `statsapi.mlb.com/api/v1/stats?stats=season&group={hitting,pitching}`.
- Un promedio de liga (`league_average_runs_per_game`) provisto por quien llama —
  este módulo **no lo calcula ni lo fetchea**. Calcular uno real requiere agregar
  las 30 franquicias, lo cual aún no se ha verificado contra un fetch en vivo
  (ver `HANDOFF.md` sección 16). Pasar aquí un número inventado sería
  exactamente el tipo de dato ficticio que el proyecto prohíbe — la
  responsabilidad de conseguir un promedio de liga real recae en quien llama,
  no en esta función.

## Disponibilidad temporal

`TeamSeasonStats` es un snapshot acumulado de temporada — no point-in-time por
juego. Usar `compute_team_run_profile` para una predicción con timestamp T
solo es válido si el `TeamSeasonStats` de entrada fue obtenido antes de T
(sin incluir el propio juego que se está prediciendo). La `provenance` del
`TeamRunProfile` resultante hereda `retrieved_at` del `TeamSeasonStats` de
origen — **no** usa la hora en que se ejecuta el cálculo — precisamente para
que un backtest pueda verificar disponibilidad temporal correctamente incluso
si el cómputo se corrió días después de haber obtenido los datos crudos.

## Fórmula

```
runs_scored_per_game   = stats.runs_scored / stats.games_played
runs_allowed_per_game  = stats.runs_allowed / stats.games_played   # total, no solo earned_runs

offensive_index        = runs_scored_per_game  / league_average_runs_per_game
run_prevention_index   = runs_allowed_per_game / league_average_runs_per_game
```

Ambos son razones a la misma tasa de liga (carreras por juego de equipo); 1.0
significa exactamente promedio. `run_prevention_index` usa carreras totales
permitidas (`runs_allowed`, campo `runs` del grupo `pitching`), no solo
carreras limpias (`earned_runs`), porque las carreras por error también
cuentan para el resultado del partido.

## Política de valores faltantes

- `stats.games_played == 0` → `ValueError` explícito. Nunca se devuelve un
  perfil con índices en 1.0 disfrazado de "promedio" cuando en realidad no hay
  datos.
- `league_average_runs_per_game <= 0` → `ValueError` (error de quien llama,
  no un caso de disponibilidad de datos).
- `data_quality = min(1.0, games_played / GAMES_FOR_FULL_CONFIDENCE)` con
  `GAMES_FOR_FULL_CONFIDENCE = 30` — un equipo con 8 juegos en abril produce
  un perfil de baja confianza, no uno falsamente seguro. Este umbral es un
  supuesto documentado, no un valor ajustado por backtest; revisar en Fase 6
  cuando haya evidencia real de cuántos juegos estabilizan la tasa de
  carreras de un equipo.
- `data_quality` alimenta directamente la puerta de calidad existente
  (`QualityGate` en `validation/quality.py`, comparado contra
  `settings.minimum_data_quality`) — no es un número decorativo.

## Versionado

Cambiar la fórmula (por ejemplo, ponderar por parques o ajustar por fuerza de
rivales) requiere: (1) incrementar `FORMULA_VERSION`, (2) actualizar esta
ficha, (3) actualizar/añadir tests. Las predicciones ya guardadas con la
versión anterior no se recalculan — se versionan, no se sobrescriben, como
exige la regla no negociable del proyecto.

## Pendiente

- Calcular `league_average_runs_per_game` real (agregando las 30 franquicias)
  en vez de dejarlo como parámetro externo — bloqueado hasta verificar el
  endpoint agregado de liga contra un fetch en vivo real.
- Ponderación por ballpark, ajuste por fuerza de calendario, y separación
  home/away quedan fuera de v1 a propósito — cada uno sería su propia ficha
  versionada, no una extensión silenciosa de esta.
