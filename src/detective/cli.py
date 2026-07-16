"""Command-line interface for Flaky Test Detective."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from detective.classify.heuristics import classify
from detective.fix.patcher import propose_fix
from detective.ingest.github_actions import ingest
from detective.models import FailureReport, FixProposal, ReproResult
from detective.pr.github_pr import open_pr
from detective.repro.runner import reproduce


COMMANDS = ("ingest", "repro", "diagnose", "fix", "run")
FIXTURES = ("shared", "race", "time")
PROJECT_DIR = Path(__file__).parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Create the detective command-line parser."""
    parser = argparse.ArgumentParser(prog="detective")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in COMMANDS:
        command_parser = subparsers.add_parser(
            command, help=f"Run the {command} stage."
        )
        if command == "run":
            group = command_parser.add_mutually_exclusive_group(required=True)
            group.add_argument("--fixture", choices=FIXTURES)
            group.add_argument("--repo", metavar="OWNER/NAME")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected pipeline-stage stub."""
    args = build_parser().parse_args(argv)
    if args.command == "run":
        if args.repo:
            return _run_repository(args.repo)
        return _run_fixture(args.fixture)

    print(f"{args.command} is not implemented yet.")
    return 0


def _run_fixture(fixture: str) -> int:
    report = _fixture_report(fixture)
    fixture_dir = PROJECT_DIR / "fixtures" / "flaky-repo"
    before = reproduce(report, fixture_dir)
    source_path = fixture_dir / report.test_id.split("::", maxsplit=1)[0]
    diagnosis = classify(before, source_path.read_text())
    proposal = propose_fix(report, diagnosis, fixture_dir)
    _print_failure_rates(before, proposal)
    return 0


def _run_repository(repository: str) -> int:
    """Run ingestion, diagnosis, fixing, and PR creation for a checkout."""
    report = ingest(repository)
    if report.test_id == "unknown":
        raise RuntimeError("ingested failure did not identify a test to reproduce")
    repo_path = PROJECT_DIR
    before = reproduce(report, repo_path)
    source_path = repo_path / report.test_id.split("::", maxsplit=1)[0]
    diagnosis = classify(before, source_path.read_text())
    proposal = propose_fix(report, diagnosis, repo_path)
    _print_failure_rates(before, proposal)
    print(open_pr(repository, repo_path, report, before, diagnosis, proposal))
    return 0


def _fixture_report(fixture: str) -> FailureReport:
    test_ids = {
        "shared": "test_shared.py::test_a_starts_with_no_shared_items",
        "race": "test_race.py::test_background_worker_completes",
        "time": "test_time.py::test_report_is_not_generated_at_midnight",
    }
    if fixture not in test_ids:
        raise ValueError(f"unsupported fixture: {fixture}")
    return FailureReport(
        test_id=test_ids[fixture],
        error_message=f"{fixture} fixture failed under perturbation",
        stack_trace="",
        run_metadata={},
    )


def _print_failure_rates(before: ReproResult, proposal: FixProposal) -> None:
    print("Perturbation | Before | After")
    print("--- | --- | ---")
    for perturbation, before_rate in before.matrix.items():
        after_rate = proposal.validation_matrix[perturbation]
        print(f"{perturbation} | {before_rate:.0%} | {after_rate:.0%}")
