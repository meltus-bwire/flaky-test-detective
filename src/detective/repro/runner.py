"""Run suspect tests repeatedly in an isolated copy of a repository."""

from pathlib import Path
from collections.abc import Callable
import os
import random
import shutil
import subprocess
from tempfile import TemporaryDirectory

from detective.models import FailureReport, ReproResult
from detective.repro.perturb import Perturbation, prepare, pytest_arguments


DEFAULT_RUNS = 20
PERTURBATIONS = tuple(Perturbation)
PROJECT_DIR = Path(__file__).parents[3]
RUN_TIMEOUT = 60.0


def reproduce(
    report: FailureReport,
    source_dir: Path,
    runs: int = DEFAULT_RUNS,
    progress: Callable[[str, int, int], None] | None = None,
) -> ReproResult:
    """Reproduce a failed test repeatedly from a temporary repository copy."""
    if runs < 1:
        raise ValueError("runs must be at least 1")

    with TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir) / source_dir.name
        shutil.copytree(
            source_dir, repo_dir, ignore=shutil.ignore_patterns(".venv", "__pycache__")
        )
        matrix: dict[str, float] = {}
        sample_failures: list[str] = []
        for perturbation in PERTURBATIONS:
            failures = _run_repeatedly(
                report.test_id, repo_dir, runs, perturbation, progress
            )
            matrix[perturbation.value] = len(failures) / runs
            sample_failures.extend(failures)

    return ReproResult(
        test_id=report.test_id,
        matrix=matrix,
        sample_failures=sample_failures,
    )


def _run_repeatedly(
    test_id: str,
    repo_dir: Path,
    runs: int,
    perturbation: Perturbation,
    progress: Callable[[str, int, int], None] | None = None,
) -> list[str]:
    prepare(perturbation, repo_dir)
    failures: list[str] = []
    for completed in range(1, runs + 1):
        seed = (
            random.randrange(2**32)
            if perturbation is Perturbation.RANDOM_ORDER
            else None
        )
        try:
            result = subprocess.run(
                _command(perturbation, test_id, seed, repo_dir),
                cwd=repo_dir,
                capture_output=True,
                check=False,
                env=_environment(perturbation, repo_dir),
                timeout=RUN_TIMEOUT,
                text=True,
            )
            if result.returncode:
                failures.append(_format_failure(result))
        except subprocess.TimeoutExpired:
            failures.append(f"pytest timed out after {RUN_TIMEOUT:.0f}s")
        if progress is not None:
            progress(perturbation.value, completed, runs)
    return failures


def _command(
    perturbation: Perturbation, test_id: str, seed: int | None, repo_dir: Path
) -> list[str]:
    arguments = pytest_arguments(perturbation, test_id, seed)
    if perturbation is Perturbation.BASELINE:
        return ["uv", "run", "pytest", *arguments]
    project = "." if (repo_dir / "pyproject.toml").exists() else str(PROJECT_DIR)
    return ["uv", "run", "--project", project, "pytest", *arguments]


def _environment(perturbation: Perturbation, repo_dir: Path) -> dict[str, str] | None:
    if perturbation not in {
        Perturbation.SCHEDULING_JITTER,
        Perturbation.CLOCK_FREEZE,
    }:
        return None
    current_path = os.environ.get("PYTHONPATH", "")
    python_path = str(repo_dir)
    if current_path:
        python_path = f"{python_path}{os.pathsep}{current_path}"
    return {**os.environ, "PYTHONPATH": python_path}


def _format_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Return useful captured output for one failed pytest invocation."""
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return output or f"pytest exited with status {result.returncode}"
