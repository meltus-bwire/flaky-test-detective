"""Command-line interface for Flaky Test Detective."""

import argparse
from collections.abc import Sequence
import inspect
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

from detective.classify.heuristics import classify
from detective.fix.patcher import propose_fix
from detective.ingest.github_actions import ingest
from detective.models import FailureReport, FixProposal, ReproResult
from detective.pr.github_pr import open_pr, render_pr_body
from detective.repro.runner import reproduce


COMMANDS = ("ingest", "repro", "diagnose", "fix", "run")
FIXTURES = ("shared", "race", "time")
PROJECT_DIR = Path(__file__).parents[2]
ORIGINAL_PROJECT_DIR = PROJECT_DIR
GREEN, RED, CYAN, RESET = ("\033[32m", "\033[31m", "\033[36m", "\033[0m") if sys.stdout.isatty() else ("", "", "", "")


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
            command_parser.add_argument(
                "--no-pr", action="store_true", help="print the PR body without posting"
            )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected pipeline-stage stub."""
    args = build_parser().parse_args(argv)
    if args.command == "run":
        if args.repo:
            return _run_repository(args.repo, args.no_pr)
        return _run_fixture(args.fixture)

    print(f"{args.command} is not implemented yet.")
    return 0


def _run_fixture(fixture: str) -> int:
    report = _fixture_report(fixture)
    fixture_dir = PROJECT_DIR / "fixtures" / "flaky-repo"
    before = _reproduce_with_progress(report, fixture_dir)
    source_path = fixture_dir / report.test_id.split("::", maxsplit=1)[0]
    diagnosis = classify(before, source_path.read_text())
    proposal = propose_fix(report, diagnosis, fixture_dir)
    _print_failure_rates(before, proposal)
    return 0


def _run_repository(repository: str, no_pr: bool = False) -> int:
    """Run ingestion, diagnosis, fixing, and PR creation for a checkout."""
    report = ingest(repository)
    if report.test_id == "unknown":
        raise RuntimeError("ingested failure did not identify a test to reproduce")
    checkout = TemporaryDirectory() if PROJECT_DIR == ORIGINAL_PROJECT_DIR else None
    try:
        repo_path = (
            Path(checkout.name) / name_from_repository(repository)
            if checkout
            else PROJECT_DIR
        )
        if checkout:
            subprocess.run(
                [
                    "git",
                    "clone",
                    f"https://github.com/{repository}.git",
                    str(repo_path),
                ],
                check=True,
            )
        before = _reproduce_with_progress(report, repo_path)
        source_path = repo_path / report.test_id.split("::", maxsplit=1)[0]
        diagnosis = classify(before, source_path.read_text())
        proposal = propose_fix(report, diagnosis, repo_path)
        _print_failure_rates(before, proposal)
        _print_diff(proposal.diff)
        if no_pr:
            print(render_pr_body(report, before, diagnosis, proposal))
            return 0
        print(open_pr(repository, repo_path, report, before, diagnosis, proposal))
        return 0
    finally:
        if checkout:
            checkout.cleanup()


def name_from_repository(repository: str) -> str:
    return repository.rsplit("/", maxsplit=1)[-1]


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
    print(f"{CYAN}Perturbation | Before | After{RESET}")
    print("--- | --- | ---")
    for perturbation, before_rate in before.matrix.items():
        after_rate = proposal.validation_matrix[perturbation]
        color = GREEN if after_rate == 0 else RED
        print(f"{perturbation} | {before_rate:.0%} | {color}{after_rate:.0%}{RESET}")


def _print_progress(perturbation: str, completed: int, total: int) -> None:
    print(f"\r{CYAN}Running {perturbation}: {completed}/{total}{RESET}", end="", flush=True)
    if completed == total:
        print()


def _reproduce_with_progress(report: FailureReport, repo_path: Path) -> ReproResult:
    """Pass progress reporting while remaining compatible with simple test doubles."""
    if "progress" in inspect.signature(reproduce).parameters:
        return reproduce(report, repo_path, progress=_print_progress)
    return reproduce(report, repo_path)


def _print_diff(diff: str) -> None:
    print("\nProposed diff\n-------------")
    print(diff.rstrip())
