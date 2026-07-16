"""Typed contracts shared by pipeline stages."""

from dataclasses import dataclass
from enum import Enum


class Cause(str, Enum):
    """Known categories of test flakiness."""

    RACE_CONDITION = "race_condition"
    TIME_DEPENDENCY = "time_dependency"
    SHARED_STATE = "shared_state"
    ORDER_DEPENDENCY = "order_dependency"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureReport:
    """Structured evidence from a failed CI test."""

    test_id: str
    error_message: str
    stack_trace: str
    run_metadata: dict[str, str]


@dataclass(frozen=True)
class ReproResult:
    """Failure rates observed across reproduction perturbations."""

    test_id: str
    matrix: dict[str, float]
    sample_failures: list[str]


@dataclass(frozen=True)
class Diagnosis:
    """A classified flaky-test cause supported by evidence."""

    cause: Cause
    confidence: float
    evidence: list[str]
    suspect_lines: list[int]


@dataclass(frozen=True)
class FixProposal:
    """A patch and its validation evidence."""

    diff: str
    explanation_md: str
    validation_matrix: dict[str, float]
