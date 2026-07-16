"""Arguments for the reproduction stage's supported perturbations."""

from enum import Enum
from pathlib import Path


class Perturbation(str, Enum):
    """The perturbations supported by the reproduction runner."""

    BASELINE = "baseline"
    RANDOM_ORDER = "random_order"
    FRESH_PROCESS = "fresh_process"
    SCHEDULING_JITTER = "scheduling_jitter"


def pytest_arguments(
    perturbation: Perturbation, test_id: str, seed: int | None = None
) -> list[str]:
    """Return pytest arguments for one perturbation."""
    if perturbation is Perturbation.BASELINE:
        return [test_id]
    if perturbation is Perturbation.RANDOM_ORDER:
        if seed is None:
            raise ValueError("random-order perturbation requires a seed")
        return [f"--randomly-seed={seed}", test_id.split("::", maxsplit=1)[0]]
    if perturbation is Perturbation.FRESH_PROCESS:
        return ["--forked", test_id]
    return [test_id]


def prepare(perturbation: Perturbation, repo_dir: Path) -> None:
    """Install any temporary files required by a perturbation."""
    if perturbation is Perturbation.SCHEDULING_JITTER:
        (repo_dir / "sitecustomize.py").write_text(_SCHEDULING_JITTER_SHIM)


_SCHEDULING_JITTER_SHIM = """import threading
import time


def _jitter(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "run":
        time.sleep(0.01)
    return _jitter


threading.settrace(_jitter)
"""
