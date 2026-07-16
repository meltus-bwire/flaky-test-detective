"""Run suspect tests repeatedly in an isolated copy of a repository."""

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from detective.models import FailureReport, ReproResult


DEFAULT_RUNS = 20
BASELINE_PERTURBATION = "baseline"


def reproduce(
    report: FailureReport, source_dir: Path, runs: int = DEFAULT_RUNS
) -> ReproResult:
    """Reproduce a failed test repeatedly from a temporary repository copy."""
    if runs < 1:
        raise ValueError("runs must be at least 1")

    with TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir) / source_dir.name
        shutil.copytree(
            source_dir, repo_dir, ignore=shutil.ignore_patterns(".venv", "__pycache__")
        )
        failures = _run_repeatedly(report.test_id, repo_dir, runs)

    return ReproResult(
        test_id=report.test_id,
        matrix={BASELINE_PERTURBATION: len(failures) / runs},
        sample_failures=failures,
    )


def _run_repeatedly(test_id: str, repo_dir: Path, runs: int) -> list[str]:
    failures: list[str] = []
    for _ in range(runs):
        result = subprocess.run(
            ["uv", "run", "pytest", test_id],
            cwd=repo_dir,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode:
            failures.append(_format_failure(result))
    return failures


def _format_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Return useful captured output for one failed pytest invocation."""
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return output or f"pytest exited with status {result.returncode}"
