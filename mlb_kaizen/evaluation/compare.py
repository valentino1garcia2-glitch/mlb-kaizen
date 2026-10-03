"""Side-by-side model comparison without declaring a winner automatically."""

from __future__ import annotations

from dataclasses import dataclass
from .walk_forward import EvaluationSummary, prediction_accuracy


@dataclass(frozen=True, slots=True)
class ModelComparison:
    summaries: tuple[EvaluationSummary, ...]

    def as_rows(self) -> tuple[dict[str, object], ...]:
        return tuple({
            "model": summary.model_name,
            "sample_size": summary.sample_size,
            "home_run_mae": summary.home_run_mae,
            "away_run_mae": summary.away_run_mae,
            "total_run_rmse": summary.total_run_rmse,
            "brier": summary.brier,
            "log_loss": summary.log_loss_value,
            "accuracy": prediction_accuracy(summary),
        } for summary in self.summaries)
