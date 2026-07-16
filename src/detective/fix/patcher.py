"""Minimal fix strategy for the shared-state fixture."""

from difflib import unified_diff
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from collections.abc import Callable
import re

from detective.models import Cause, Diagnosis, FailureReport, FixProposal
from detective.repro.runner import DEFAULT_RUNS, reproduce


def propose_fix(
    report: FailureReport,
    diagnosis: Diagnosis,
    source_dir: Path,
    runs: int = DEFAULT_RUNS,
) -> FixProposal:
    """Propose and validate a cause-specific fixture fix."""
    strategies: dict[Cause, Callable[[str], str]] = {
        Cause.SHARED_STATE: _add_reset_fixture,
        Cause.RACE_CONDITION: _add_race_wait,
        Cause.TIME_DEPENDENCY: _add_time_fixture,
    }
    strategy = strategies.get(diagnosis.cause)
    if strategy is None:
        raise ValueError("v2 patcher does not support this diagnosis")

    relative_path = Path(report.test_id.split("::", maxsplit=1)[0])
    original = (source_dir / relative_path).read_text()
    with TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir) / source_dir.name
        shutil.copytree(
            source_dir, repo_dir, ignore=shutil.ignore_patterns(".venv", "__pycache__")
        )
        patched_path = repo_dir / relative_path
        patched = strategy(patched_path.read_text())
        patched_path.write_text(patched)
        validation_matrix = reproduce(report, repo_dir, runs).matrix

    if any(rate > 0 for rate in validation_matrix.values()):
        raise RuntimeError("shared-state fix did not pass matrix validation")

    return FixProposal(
        diff=_diff(relative_path, original, patched),
        explanation_md=_explanation(diagnosis.cause),
        validation_matrix=validation_matrix,
    )


def _add_reset_fixture(source: str) -> str:
    match = re.search(r"(\w+)\.clear\(\)", source)
    if not match:
        match = re.search(r"(\w+)\s*:\s*list(?:\[|\s*=)", source)
    if not match:
        raise ValueError("shared-state strategy requires a mutable state .clear() call")
    state_name = match.group(1)
    pytest_import = "" if "import pytest" in source else "import pytest\n\n"
    fixture = (
        "\n\n@pytest.fixture(autouse=True)\n"
        "def reset_shared_items() -> None:\n"
        f"    {state_name}.clear()\n"
    )
    return f"{pytest_import}{source.rstrip()}{fixture}"


def _add_race_wait(source: str) -> str:
    if "worker.start()" not in source:
        raise ValueError("race strategy requires worker.start()")
    start = re.search(r"(\w+)\.start\(\)", source)
    result = re.search(r"(\w+)\s*=\s*\[", source)
    if not start or not result:
        raise ValueError("race strategy requires a worker and result list")
    source = source.replace(
        f"{start.group(1)}.start()",
        f"{start.group(1)}.start()\n    _wait_for_result({result.group(1)})",
        1,
    )
    if "import time" not in source:
        source = f"import time\n\n{source}"
    helper = (
        "\n\ndef _wait_for_result(values: list[str], timeout: float = 1.0) -> None:\n"
        "    deadline = time.monotonic() + timeout\n"
        "    while not values and time.monotonic() < deadline:\n"
        "        time.sleep(0.001)\n"
    )
    return f"{source.rstrip()}{helper}"


def _add_time_fixture(source: str) -> str:
    pytest_import = "" if "import pytest" in source else "import pytest\n\n"
    fixture = (
        "\n\nclass _FixedDateTime(datetime):\n"
        "    @classmethod\n"
        "    def now(cls, tz=None):\n"
        "        return cls(2026, 1, 1, 12, 0, tzinfo=tz)\n"
        "\n\n@pytest.fixture(autouse=True)\n"
        "def freeze_time(monkeypatch):\n"
        '    monkeypatch.setattr(__name__ + ".datetime", _FixedDateTime)\n'
    )
    return f"{pytest_import}{source.rstrip()}{fixture}"


def _explanation(cause: Cause) -> str:
    explanations = {
        Cause.SHARED_STATE: "Added an autouse fixture that clears shared test state before each test.",
        Cause.RACE_CONDITION: "Added a bounded polling wait for the background worker result.",
        Cause.TIME_DEPENDENCY: "Added an autouse fixture that freezes the test clock to a stable time.",
    }
    return explanations[cause]


def _diff(relative_path: Path, original: str, patched: str) -> str:
    return "".join(
        unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )
