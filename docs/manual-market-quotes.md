# Cuotas introducidas manualmente

`record-market-quote` guarda una observación de una cuota que el usuario vio
en una casa de apuestas. Es un registro histórico **append-only**: una cuota
nueva nunca reemplaza una observación anterior.

Cada registro exige una hora con zona horaria mediante `--observed-at`. Esa
hora significa exactamente “cuándo se vio esta cuota”; no declara por sí sola
que sea la cuota de apertura ni la de cierre.

Ejemplo:

```powershell
.\.venv\Scripts\python.exe -m mlb_kaizen.interface.cli record-market-quote `
  --game-id mlb:849826 --sportsbook Playdoit --market moneyline `
  --selection away --american-odds +120 `
  --observed-at 2026-10-07T01:25:00+00:00 --source user_playdoit
```

Mercados aceptados:

- `moneyline`: `--selection home` o `away`; sin `--line`.
- `total`: `--selection over` o `under`; requiere `--line`, por ejemplo `7.5`.
- `run_line`: `--selection home` o `away`; requiere `--line`, por ejemplo `+1.5`.

Puede usarse `--american-odds` o `--decimal-odds`, pero nunca ambos. El precio
americano original se conserva en el `payload` para auditoría, mientras que el
precio decimal permite hacer comparaciones matemáticas consistentes.

## Qué permite y qué no permite

Una sola captura sólo acredita una cuota vista. Para hablar de movimiento de
precio o CLV se necesitan, como mínimo, dos observaciones con hora: una antes
del juego y otra identificable como la última observada antes del inicio. Tras
el partido, el resultado se agrega separadamente con `record-result`.

El registro de cuotas no genera una recomendación y no convierte al modelo en
rentable. En particular, el artefacto E11 está bloqueado para playoffs hasta
que exista un modelo de playoffs validado por separado.
