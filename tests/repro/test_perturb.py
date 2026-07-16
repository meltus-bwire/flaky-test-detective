from pathlib import Path

import pytest

from detective.repro.perturb import Perturbation, prepare, pytest_arguments


def test_random_order_runs_the_test_file_with_a_seed() -> None:
    assert pytest_arguments(
        Perturbation.RANDOM_ORDER, "tests/test_shared.py::test_starts_empty", seed=17
    ) == ["--randomly-seed=17", "tests/test_shared.py"]


def test_random_order_requires_a_seed() -> None:
    with pytest.raises(ValueError, match="requires a seed"):
        pytest_arguments(
            Perturbation.RANDOM_ORDER, "tests/test_shared.py::test_starts_empty"
        )


def test_fresh_process_runs_the_suspect_test() -> None:
    test_id = "tests/test_shared.py::test_starts_empty"

    assert pytest_arguments(Perturbation.FRESH_PROCESS, test_id) == [
        "--forked",
        test_id,
    ]


def test_scheduling_jitter_installs_a_thread_trace_shim(tmp_path: Path) -> None:
    prepare(Perturbation.SCHEDULING_JITTER, tmp_path)

    shim = (tmp_path / "sitecustomize.py").read_text()

    assert "threading.settrace(_jitter)" in shim
    assert "time.sleep(0.01)" in shim
