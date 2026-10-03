# League average runs per game

Version: `LEAGUE-AVG-RUNS-0.1`

## Definition

For a season response containing team splits:

`league_average_runs_per_game = sum(runs_scored_all_teams) / sum(games_played_all_teams)`

The provider requires at least 28 distinct team splits and rejects duplicate team IDs. This avoids
silently averaging a truncated response while remaining tolerant of a future league expansion.

## Temporal use

For live analysis, the value is the provider snapshot retrieved for the requested season.
For historical evaluation, use the league-average snapshot whose retrieval/known timestamp satisfies
the point-in-time cutoff for the prediction row.
