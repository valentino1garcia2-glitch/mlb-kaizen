# Odds provider

Current adapter: `SportsGameOddsProvider` (`mlb_kaizen/data/odds.py`).

The current API documentation describes `/v2/events`, `leagueID=MLB`, `oddsAvailable=true`, `oddID`,
`includeAltLines=true`, and bookmaker-specific odds under `odds.<oddID>.byBookmaker.<bookmakerID>`.
The adapter normalizes full-game moneyline (`ml`), spread/run-line (`sp`) and total (`ou`) observations.

The adapter is code-complete but **live verification remains environment-dependent**: a real API key and
live request are required before the provider can be marked production-verified.

## Credentials

Set:

```text
MLB_KAIZEN_SGO_API_KEY
MLB_KAIZEN_SGO_BOOKMAKERS=book1,book2
```

The API key must never be committed or logged.

## Terms note

The provider's current terms restrict resale/redistribution and explicitly restrict using the service/data
to train ML models that replicate or compete with the provider. They also impose rate/access limits and
require the key to remain confidential. Treat those terms as an integration gate before production use.

This repository does not use the provider as a label to train a model that reproduces the provider's own
service; odds are treated as market inputs to KAIZEN's independent analysis. Legal/compliance review remains
separate from the codebase.
