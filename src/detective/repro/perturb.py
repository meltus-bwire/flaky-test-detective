"""Arguments for the reproduction stage's supported perturbations."""

from enum import Enum
from pathlib import Path


class Perturbation(str, Enum):
    """The perturbations supported by the reproduction runner."""

    BASELINE = "baseline"
    RANDOM_ORDER = "random_order"
    FRESH_PROCESS = "fresh_process"
    SCHEDULING_JITTER = "scheduling_jitter"
    CLOCK_FREEZE = "clock_freeze"


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
    if perturbation is Perturbation.CLOCK_FREEZE:
        (repo_dir / "sitecustomize.py").write_text(_CLOCK_FREEZE_SHIM)


_SCHEDULING_JITTER_SHIM = """import threading
import time


def _jitter(frame, event, arg):
    if event == "call" and frame.f_code.co_name == "run":
        time.sleep(0.01)
    return _jitter


threading.settrace(_jitter)
"""


_CLOCK_FREEZE_SHIM = """import datetime as _datetime
import sys
import types


class _FrozenDateTime(_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 1, 0, 0, tzinfo=tz)


_module = types.ModuleType("datetime")
for _name in dir(_datetime):
    setattr(_module, _name, getattr(_datetime, _name))
_module.datetime = _FrozenDateTime
sys.modules["datetime"] = _module
"""
