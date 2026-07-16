"""Validate structured verdicts returned by an optional LLM classifier."""

import json
from collections.abc import Mapping
from typing import Any

from detective.models import Cause, Diagnosis


def parse_verdict(response: str | Mapping[str, Any]) -> Diagnosis:
    """Parse and validate an LLM verdict before it enters the pipeline."""
    payload: Any = json.loads(response) if isinstance(response, str) else response
    if not isinstance(payload, Mapping):
        raise ValueError("LLM verdict must be a JSON object")
    try:
        cause = Cause(payload["cause"])
        confidence = float(payload["confidence"])
        evidence = payload["evidence"]
        suspect_lines = payload["suspect_lines"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("LLM verdict has an invalid schema") from error
    if cause is Cause.UNKNOWN or not 0.0 <= confidence <= 1.0:
        raise ValueError("LLM verdict must name a known cause and valid confidence")
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) for item in evidence
    ):
        raise ValueError("LLM evidence must be a list of strings")
    if not isinstance(suspect_lines, list) or not all(
        isinstance(line, int) and line > 0 for line in suspect_lines
    ):
        raise ValueError("LLM suspect_lines must contain positive integers")
    return Diagnosis(cause, confidence, evidence, suspect_lines)
