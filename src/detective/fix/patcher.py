"""Minimal fix strategy for the shared-state fixture."""

from difflib import unified_diff
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from detective.models import Cause, Diagnosis, FailureReport, FixProposal
from detective.repro.runner import DEFAULT_RUNS, reproduce


def propose_fix(
    report: FailureReport,
    diagnosis: Diagnosis,
    source_dir: Path,
    runs: int = DEFAULT_RUNS,
) -> FixProposal:
    """Propose and validate the shared-state reset-fixture fix."""
    if diagnosis.cause is not Cause.SHARED_STATE:
        raise ValueError("v1 patcher only supports shared-state diagnoses")

    relative_path = Path(report.test_id.split("::", maxsplit=1)[0])
    original = (source_dir / relative_path).read_text()
    with TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir) / source_dir.name
        shutil.copytree(
            source_dir, repo_dir, ignore=shutil.ignore_patterns(".venv", "__pycache__")
        )
        patched_path = repo_dir / relative_path
        patched = _add_reset_fixture(patched_path.read_text())
        patched_path.write_text(patched)
        validation_matrix = reproduce(report, repo_dir, runs).matrix

    if any(rate > 0 for rate in validation_matrix.values()):
        raise RuntimeError("shared-state fix did not pass matrix validation")

    return FixProposal(
        diff=_diff(relative_path, original, patched),
        explanation_md="Added an autouse fixture that clears shared test state before each test.",
        validation_matrix=validation_matrix,
    )


def _add_reset_fixture(source: str) -> str:
    pytest_import = "" if "import pytest" in source else "import pytest\n\n"
    fixture = (
        "\n\n@pytest.fixture(autouse=True)\n"
        "def reset_shared_items() -> None:\n"
        "    seen_items.clear()\n"
    )
    return f"{pytest_import}{source.rstrip()}{fixture}"


def _diff(relative_path: Path, original: str, patched: str) -> str:
    return "".join(
        unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )
