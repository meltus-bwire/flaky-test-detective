"""Command-line interface for Flaky Test Detective."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from detective.classify.heuristics import classify
from detective.fix.patcher import propose_fix
from detective.models import FailureReport, FixProposal, ReproResult
from detective.repro.runner import reproduce


COMMANDS = ("ingest", "repro", "diagnose", "fix", "run")
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
            command_parser.add_argument("--fixture", choices=("shared",), required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected pipeline-stage stub."""
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _run_fixture(args.fixture)

    print(f"{args.command} is not implemented yet.")
    return 0


def _run_fixture(fixture: str) -> int:
    report = _fixture_report(fixture)
    fixture_dir = PROJECT_DIR / "fixtures" / "flaky-repo"
    before = reproduce(report, fixture_dir)
    diagnosis = classify(before)
    proposal = propose_fix(report, diagnosis, fixture_dir)
    _print_failure_rates(before, proposal)
    return 0


def _fixture_report(fixture: str) -> FailureReport:
    if fixture != "shared":
        raise ValueError(f"unsupported fixture: {fixture}")
    return FailureReport(
        test_id="test_shared.py::test_a_starts_with_no_shared_items",
        error_message="shared state leaked from another test",
        stack_trace="",
        run_metadata={},
    )


def _print_failure_rates(before: ReproResult, proposal: FixProposal) -> None:
    print("Perturbation | Before | After")
    print("--- | --- | ---")
    for perturbation, before_rate in before.matrix.items():
        after_rate = proposal.validation_matrix[perturbation]
        print(f"{perturbation} | {before_rate:.0%} | {after_rate:.0%}")
