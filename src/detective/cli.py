"""Command-line interface for Flaky Test Detective."""

import argparse
from collections.abc import Sequence


COMMANDS = ("ingest", "repro", "diagnose", "fix", "run")


def build_parser() -> argparse.ArgumentParser:
    """Create the detective command-line parser."""
    parser = argparse.ArgumentParser(prog="detective")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in COMMANDS:
        subparsers.add_parser(command, help=f"Run the {command} stage.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected pipeline-stage stub."""
    args = build_parser().parse_args(argv)
    print(f"{args.command} is not implemented yet.")
    return 0
