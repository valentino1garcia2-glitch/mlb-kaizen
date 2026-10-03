# Snapshot policy

The project stores observations append-only. A changed provider response is a new observation, not an
update to the previous record.

Recommended pregame checkpoints:

- T-24h or first available;
- T-6h;
- T-3h;
- T-1h;
- T-30m / final pregame window;
- postgame result snapshot.

Not every source needs every checkpoint. The point is to preserve what was known and when it was known.
If a source is unavailable at a checkpoint, store the absence when the domain contract supports it.

For backtesting, select only snapshots whose `retrieved_at` / `effective_at` prove that the information
was available at or before the prediction timestamp.
