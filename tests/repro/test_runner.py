from pathlib import Path
import subprocess

import pytest

from detective.models import FailureReport
from detective.repro.runner import BASELINE_PERTURBATION, reproduce


def test_reproduce_runs_in_a_temporary_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "fixture"
    source_dir.mkdir()
    (source_dir / "test_example.py").write_text("def test_example(): pass\n")
    report = FailureReport("test_example.py::test_example", "failed", "trace", {})
    calls: list[tuple[list[str], Path]] = []
    results = iter(
        [
            subprocess.CompletedProcess([], 0, "passed", ""),
            subprocess.CompletedProcess([], 1, "failed", "details"),
            subprocess.CompletedProcess([], 1, "", "more details"),
        ]
    )

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        cwd = kwargs["cwd"]
        assert isinstance(cwd, Path)
        assert cwd != source_dir
        assert (cwd / "test_example.py").exists()
        calls.append((command, cwd))
        return next(results)

    monkeypatch.setattr("detective.repro.runner.subprocess.run", run)

    result = reproduce(report, source_dir, runs=3)

    assert result.matrix == {BASELINE_PERTURBATION: pytest.approx(2 / 3)}
    assert result.sample_failures == ["failed\ndetails", "more details"]
    assert [command for command, _ in calls] == [
        ["uv", "run", "pytest", report.test_id]
    ] * 3


def test_reproduce_rejects_non_positive_run_counts(tmp_path: Path) -> None:
    report = FailureReport("test_example.py::test_example", "failed", "trace", {})

    with pytest.raises(ValueError, match="at least 1"):
        reproduce(report, tmp_path, runs=0)
