"""Arguments for the reproduction stage's supported perturbations."""

from enum import Enum


class Perturbation(str, Enum):
    """The perturbations supported by the reproduction runner."""

    BASELINE = "baseline"
    RANDOM_ORDER = "random_order"
    FRESH_PROCESS = "fresh_process"


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
    return ["--forked", test_id]
