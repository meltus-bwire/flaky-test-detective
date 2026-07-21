from pathlib import Path

import pytest

from detective.cli import COMMANDS, main
from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult


@pytest.mark.parametrize("command", COMMANDS[:-1])
def test_stage_command_reports_stub(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command]) == 0
    assert capsys.readouterr().out == f"{command} is not implemented yet.\n"

def test_cli_requires_subcommand()->None:
    with pytest.raises(SystemExit, match='2'):
        main([])

def test_run_shared_fixture_prints_before_and_after_rates(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    before = ReproResult(
        "test_shared.py::test_a_starts_with_no_shared_items",
        {"baseline": 0.0, "random_order": 0.5, "fresh_process": 0.0},
        [],
    )
    proposal = FixProposal(
        "diff",
        "explanation",
        {"baseline": 0.0, "random_order": 0.0, "fresh_process": 0.0},
    )

    def reproduce_fixture(report: FailureReport, source_dir: Path) -> ReproResult:
        assert report.test_id == before.test_id
        assert source_dir.name == "flaky-repo"
        return before

    monkeypatch.setattr("detective.cli.reproduce", reproduce_fixture)
    monkeypatch.setattr(
        "detective.cli.classify",
        lambda *_: Diagnosis(Cause.SHARED_STATE, 0.8, [], []),
    )
    monkeypatch.setattr(
        "detective.cli.analyze",
        lambda report, result, source, heuristic: Diagnosis(
            Cause.SHARED_STATE, 0.8, [], []
        ),
    )
    monkeypatch.setattr("detective.cli.propose_fix", lambda *_: proposal)

    assert main(["run", "--fixture", "shared"]) == 0
    assert capsys.readouterr().out == (
        "Perturbation | Before | After\n"
        "--- | --- | ---\n"
        "baseline | 0% | 0%\n"
        "random_order | 50% | 0%\n"
        "fresh_process | 0% | 0%\n"
    )
