from detective.cli import main
from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult


def test_run_repo_wires_pipeline(monkeypatch, tmp_path, capsys) -> None:
    report = FailureReport("tests/test.py::test_case", "boom", "", {})
    repro = ReproResult(report.test_id, {"baseline": 1.0}, [])
    diagnosis = Diagnosis(Cause.SHARED_STATE, 1.0, [], [])
    proposal = FixProposal("diff", "fixed", {"baseline": 0.0})
    calls: list[str] = []

    monkeypatch.setattr("detective.cli.PROJECT_DIR", tmp_path)
    monkeypatch.setattr(
        "detective.cli.ingest", lambda repo: calls.append(repo) or report
    )
    monkeypatch.setattr("detective.cli.reproduce", lambda r, path: repro)
    monkeypatch.setattr("detective.cli.classify", lambda result, source: diagnosis)
    monkeypatch.setattr("detective.cli.propose_fix", lambda r, d, path: proposal)
    monkeypatch.setattr(
        "detective.cli.open_pr",
        lambda repo, path, r, b, d, p: "https://example.test/pr/1",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test.py").write_text("def test_case(): pass")

    assert main(["run", "--repo", "owner/name"]) == 0
    assert calls == ["owner/name"]
    assert "https://example.test/pr/1" in capsys.readouterr().out


def test_run_repo_no_pr_prints_body(monkeypatch, tmp_path, capsys) -> None:
    report = FailureReport("tests/test.py::test_case", "boom", "", {})
    repro = ReproResult(report.test_id, {"baseline": 1.0}, [])
    diagnosis = Diagnosis(Cause.SHARED_STATE, 1.0, [], [])
    proposal = FixProposal("diff", "fixed", {"baseline": 0.0})
    monkeypatch.setattr("detective.cli.PROJECT_DIR", tmp_path)
    monkeypatch.setattr("detective.cli.ingest", lambda repo: report)
    monkeypatch.setattr("detective.cli.reproduce", lambda r, path: repro)
    monkeypatch.setattr("detective.cli.classify", lambda result, source: diagnosis)
    monkeypatch.setattr("detective.cli.propose_fix", lambda r, d, path: proposal)
    monkeypatch.setattr(
        "detective.cli.open_pr", lambda *args: (_ for _ in ()).throw(AssertionError())
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test.py").write_text("def test_case(): pass")

    assert main(["run", "--repo", "owner/name", "--no-pr"]) == 0
    assert "## Flaky test" in capsys.readouterr().out
