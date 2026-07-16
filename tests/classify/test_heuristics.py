import pytest

from detective.classify.heuristics import classify
from detective.models import Cause, Diagnosis, ReproResult


def test_classify_labels_random_order_only_failures_as_shared_state() -> None:
    result = ReproResult(
        test_id="test_shared.py::test_a_starts_with_no_shared_items",
        matrix={"baseline": 0.0, "random_order": 0.5, "fresh_process": 0.0},
        sample_failures=["assert [] == ['item']"],
    )

    diagnosis = classify(result)

    assert diagnosis.cause is Cause.SHARED_STATE
    assert diagnosis.confidence == 0.8
    assert diagnosis.evidence == [
        "Random order failed 50% of runs while baseline and fresh-process runs had no "
        "failures."
    ]


@pytest.mark.parametrize(
    "matrix",
    [
        {"baseline": 0.5, "random_order": 0.5, "fresh_process": 0.0},
        {"baseline": 0.0, "random_order": 0.0, "fresh_process": 0.0},
        {"random_order": 1.0},
    ],
)
def test_classify_leaves_ambiguous_matrices_unknown(matrix: dict[str, float]) -> None:
    diagnosis = classify(ReproResult("test_example.py::test_example", matrix, []))

    assert diagnosis.cause is Cause.UNKNOWN
    assert diagnosis.confidence == 0.0


def test_classify_uses_fallback_for_unknown() -> None:
    result = ReproResult("test_example.py::test_example", {"baseline": 0.2}, [])

    def fallback(_result, _source):
        return Diagnosis(Cause.ORDER_DEPENDENCY, 0.7, ["order"], [3])

    assert classify(result, fallback=fallback).cause is Cause.ORDER_DEPENDENCY


def test_classify_identifies_time_dependency_from_clock_and_source() -> None:
    result = ReproResult(
        "test_time.py::test_report",
        {"baseline": 0.0, "clock_freeze": 1.0},
        [],
    )
    source = "from datetime import datetime\nassert datetime.now().hour != 0\n"

    diagnosis = classify(result, source)

    assert diagnosis.cause is Cause.TIME_DEPENDENCY
    assert diagnosis.suspect_lines == [2]


def test_classify_identifies_race_from_jitter_and_thread_signal() -> None:
    result = ReproResult(
        "test_race.py::test_worker",
        {"baseline": 0.0, "scheduling_jitter": 1.0},
        [],
    )
    source = (
        "from threading import Thread\nworker = Thread(target=work)\nassert result\n"
    )

    diagnosis = classify(result, source)

    assert diagnosis.cause is Cause.RACE_CONDITION
    assert diagnosis.suspect_lines == [1, 2]
