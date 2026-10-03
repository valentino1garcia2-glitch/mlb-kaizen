"""Human-vs-machine decision scoring and compact leaderboard summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class PickOutcome:
    status: str
    correct: bool | None
    pnl: float | None = None


def evaluate_pick(pick: dict[str, Any] | None, home_score: int, away_score: int) -> PickOutcome:
    if not pick:
        return PickOutcome("missing", None, None)
    market = str(pick.get("market", ""))
    selection = str(pick.get("selection", ""))
    line = pick.get("line")
    decimal_odds = pick.get("decimal_odds")
    odds = None if decimal_odds is None else float(decimal_odds)

    def settled(correct: bool) -> PickOutcome:
        if odds is None:
            return PickOutcome("settled", correct, None)
        return PickOutcome("settled", correct, (odds - 1.0) if correct else -1.0)

    if market == "moneyline":
        if home_score == away_score:
            return PickOutcome("push", None, 0.0 if odds is not None else None)
        winner = "home" if home_score > away_score else "away"
        return settled(selection == winner)
    if line is None:
        return PickOutcome("unscorable", None, None)
    line = float(line)
    if market == "total":
        value = home_score + away_score
        threshold = "over" if value > line else "under" if value < line else "push"
        if threshold == "push":
            return PickOutcome("push", None, 0.0 if odds is not None else None)
        return settled(selection == threshold)
    if market == "run_line":
        adjusted = home_score + line if selection == "home" else away_score + line
        opponent = away_score if selection == "home" else home_score
        if adjusted == opponent:
            return PickOutcome("push", None, 0.0 if odds is not None else None)
        return settled(adjusted > opponent)
    return PickOutcome("unscorable", None, None)


def leaderboard(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    machine_correct = human_correct = 0
    machine_settled = human_settled = 0
    machine_pnl = human_pnl = 0.0
    machine_pnl_count = human_pnl_count = 0
    pairs: list[dict[str, Any]] = []
    for row in rows:
        result = row.get("result") or {}
        if "home_score" not in result or "away_score" not in result:
            pairs.append({**row, "machine_outcome": {"status": "pending", "correct": None}, "human_outcome": {"status": "pending", "correct": None}})
            continue
        machine = evaluate_pick(row.get("machine_pick"), int(result["home_score"]), int(result["away_score"]))
        human = evaluate_pick(row.get("human_pick"), int(result["home_score"]), int(result["away_score"]))
        if machine.correct is not None:
            machine_settled += 1
            machine_correct += int(machine.correct)
        if human.correct is not None:
            human_settled += 1
            human_correct += int(human.correct)
        if machine.pnl is not None:
            machine_pnl += machine.pnl
            machine_pnl_count += 1
        if human.pnl is not None:
            human_pnl += human.pnl
            human_pnl_count += 1
        pairs.append({**row, "machine_outcome": {"status": machine.status, "correct": machine.correct}, "human_outcome": {"status": human.status, "correct": human.correct}})
    return {
        "records": len(pairs),
        "machine_correct": machine_correct,
        "machine_settled": machine_settled,
        "machine_accuracy": machine_correct / machine_settled if machine_settled else None,
        "human_correct": human_correct,
        "human_settled": human_settled,
        "human_accuracy": human_correct / human_settled if human_settled else None,
        "machine_pnl": machine_pnl if machine_pnl_count else None,
        "machine_pnl_count": machine_pnl_count,
        "human_pnl": human_pnl if human_pnl_count else None,
        "human_pnl_count": human_pnl_count,
        "rows": pairs,
    }
