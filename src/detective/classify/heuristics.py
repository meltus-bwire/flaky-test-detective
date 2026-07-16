"""Deterministic classification rules for reproduction results."""

from detective.models import Cause, Diagnosis, ReproResult


def classify(result: ReproResult, source: str | None = None) -> Diagnosis:
    """Classify a reproduction matrix with optional static source signals."""
    if source is not None:
        diagnosis = _classify_static_signals(result, source)
        if diagnosis is not None:
            return diagnosis

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
        evidence=["The reproduction matrix and source do not match a known heuristic."],
        suspect_lines=[],
    )


def _classify_static_signals(result: ReproResult, source: str) -> Diagnosis | None:
    time_lines = _near_assertion_lines(
        source, ("datetime.now(", "datetime.utcnow(", "time.time(")
    )
    if result.matrix.get("clock_freeze", 0.0) > 0 and time_lines:
        return Diagnosis(
            cause=Cause.TIME_DEPENDENCY,
            confidence=0.9,
            evidence=[
                "Clock freezing failed and a time lookup appears near an assertion."
            ],
            suspect_lines=time_lines,
        )

    race_lines = _race_signal_lines(source)
    if result.matrix.get("scheduling_jitter", 0.0) > 0 and race_lines:
        return Diagnosis(
            cause=Cause.RACE_CONDITION,
            confidence=0.9,
            evidence=[
                "Scheduling jitter failed and the test contains concurrency timing signals."
            ],
            suspect_lines=race_lines,
        )
    return None


def _near_assertion_lines(source: str, signals: tuple[str, ...]) -> list[int]:
    lines = source.splitlines()
    signal_lines = [
        number
        for number, line in enumerate(lines, 1)
        if any(signal in line for signal in signals)
    ]
    assertion_lines = [
        number for number, line in enumerate(lines, 1) if "assert " in line
    ]
    return [
        number
        for number in signal_lines
        if any(abs(number - assertion) <= 2 for assertion in assertion_lines)
    ]


def _race_signal_lines(source: str) -> list[int]:
    lines = source.splitlines()
    signals = ("Thread", "threading.", "asyncio.gather(", "time.sleep(")
    thread_lines = [
        number
        for number, line in enumerate(lines, 1)
        if any(signal in line for signal in signals)
    ]
    sleep_lines = [
        number for number, line in enumerate(lines, 1) if "time.sleep(" in line
    ]
    assertion_lines = [
        number for number, line in enumerate(lines, 1) if "assert " in line
    ]
    near_sleep = [
        number
        for number in sleep_lines
        if any(abs(number - assertion) <= 2 for assertion in assertion_lines)
    ]
    return sorted(set(thread_lines + near_sleep))
