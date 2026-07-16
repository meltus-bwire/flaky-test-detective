from pathlib import Path

import pytest

from detective.fix.patcher import propose_fix
from detective.models import Cause, Diagnosis, FailureReport, ReproResult


def test_propose_fix_patches_and_validates_a_temporary_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "fixture"
    source_dir.mkdir()
    test_path = source_dir / "test_shared.py"
    test_path.write_text("seen_items: list[str] = []\n")
    report = FailureReport("test_shared.py::test_a", "failed", "trace", {})
    diagnosis = Diagnosis(Cause.SHARED_STATE, 0.8, [], [])

    def reproduce_patched_copy(
        report: FailureReport, copied_dir: Path, runs: int
    ) -> ReproResult:
        patched = (copied_dir / "test_shared.py").read_text()
        assert copied_dir != source_dir
        assert "@pytest.fixture(autouse=True)" in patched
        assert "seen_items.clear()" in patched
        return ReproResult(report.test_id, {"baseline": 0.0, "random_order": 0.0}, [])

    monkeypatch.setattr("detective.fix.patcher.reproduce", reproduce_patched_copy)

    proposal = propose_fix(report, diagnosis, source_dir, runs=3)

    assert test_path.read_text() == "seen_items: list[str] = []\n"
    assert "@pytest.fixture(autouse=True)" in proposal.diff
    assert proposal.validation_matrix == {"baseline": 0.0, "random_order": 0.0}


def test_propose_fix_rejects_unsupported_diagnoses(tmp_path: Path) -> None:
    report = FailureReport("test_shared.py::test_a", "failed", "trace", {})
    diagnosis = Diagnosis(Cause.UNKNOWN, 0.0, [], [])

    with pytest.raises(ValueError, match="only supports shared-state"):
        propose_fix(report, diagnosis, tmp_path)


def test_propose_fix_rejects_failed_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "fixture"
    source_dir.mkdir()
    (source_dir / "test_shared.py").write_text("seen_items: list[str] = []\n")
    report = FailureReport("test_shared.py::test_a", "failed", "trace", {})
    diagnosis = Diagnosis(Cause.SHARED_STATE, 0.8, [], [])
    failed_result = ReproResult(report.test_id, {"random_order": 0.5}, ["failed"])
    monkeypatch.setattr("detective.fix.patcher.reproduce", lambda *_: failed_result)

    with pytest.raises(RuntimeError, match="did not pass matrix validation"):
        propose_fix(report, diagnosis, source_dir)
