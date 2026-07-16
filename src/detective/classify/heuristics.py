"""Deterministic classification rules for reproduction results."""

from detective.models import Cause, Diagnosis, ReproResult


def classify(result: ReproResult) -> Diagnosis:
    """Classify a reproduction matrix using the available v1 heuristic."""
    random_order_rate = result.matrix.get("random_order", 0.0)
    baseline_rate = result.matrix.get("baseline")
    fresh_process_rate = result.matrix.get("fresh_process")

    if random_order_rate > 0 and baseline_rate == 0 and fresh_process_rate == 0:
        return Diagnosis(
            cause=Cause.SHARED_STATE,
            confidence=0.8,
            evidence=[
                "Random order failed "
                f"{random_order_rate:.0%} of runs while baseline and fresh-process "
                "runs had no failures."
            ],
            suspect_lines=[],
        )

    return Diagnosis(
        cause=Cause.UNKNOWN,
        confidence=0.0,
        evidence=["The reproduction matrix does not match a known v1 heuristic."],
        suspect_lines=[],
    )
