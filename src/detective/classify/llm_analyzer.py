"""OpenAI-powered diagnosis and reviewer explanations for flaky tests."""

import json
from collections.abc import Mapping
from typing import Any

from openai import OpenAI
from openai.types.responses import ResponseTextConfigParam
from dotenv import load_dotenv

from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult


DEFAULT_MODEL = "gpt-5-mini"


def load_config() -> None:
    """Load local OpenAI configuration when a default client is needed."""
    load_dotenv()


def analyze(
    report: FailureReport,
    result: ReproResult,
    source: str,
    heuristic: Diagnosis,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
) -> Diagnosis:
    """Use an OpenAI model to diagnose a flake from its evidence."""
    response = _client(client).responses.create(
        model=model,
        instructions=(
            "You diagnose flaky pytest tests. Use only the supplied evidence. "
            "Choose the most likely cause and cite source line numbers when useful. "
            "Return JSON that exactly matches the requested schema."
        ),
        input=_diagnosis_context(report, result, source, heuristic),
        text=_diagnosis_schema(),
    )
    return parse_verdict(response.output_text)


def explain_for_review(
    report: FailureReport,
    repro: ReproResult,
    diagnosis: Diagnosis,
    proposal: FixProposal,
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Write a concise, plain-language explanation for a generated PR."""
    response = _client(client).responses.create(
        model=model,
        instructions=(
            "Write a clear GitHub pull-request explanation for a developer. "
            "Use plain language, explain what could go wrong before this change, "
            "what changed, and why the verification is trustworthy. Do not claim "
            "anything that is not in the evidence. Return Markdown only, with no title."
        ),
        input=_review_context(report, repro, diagnosis, proposal),
    )
    explanation = response.output_text.strip()
    if not explanation:
        raise ValueError("OpenAI returned an empty PR explanation")
    return explanation


def _client(client: OpenAI | None) -> OpenAI:
    if client is not None:
        return client
    load_config()
    return OpenAI()


def parse_verdict(response: str | Mapping[str, Any]) -> Diagnosis:
    """Parse and validate an LLM verdict before it enters the pipeline."""
    payload: Any = json.loads(response) if isinstance(response, str) else response
    if not isinstance(payload, Mapping):
        raise ValueError("LLM verdict must be a JSON object")
    required_fields = {"cause", "confidence", "evidence", "suspect_lines"}
    if set(payload) != required_fields:
        raise ValueError("LLM verdict has an invalid schema")
    try:
        cause = Cause(payload["cause"])
        raw_confidence = payload["confidence"]
        evidence = payload["evidence"]
        suspect_lines = payload["suspect_lines"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("LLM verdict has an invalid schema") from error
    if not isinstance(raw_confidence, int | float) or isinstance(raw_confidence, bool):
        raise ValueError("LLM verdict has an invalid schema")
    confidence = float(raw_confidence)
    if cause is Cause.UNKNOWN or not 0.0 <= confidence <= 1.0:
        raise ValueError("LLM verdict must name a known cause and valid confidence")
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) for item in evidence
    ):
        raise ValueError("LLM evidence must be a list of strings")
    if not isinstance(suspect_lines, list) or not all(
        isinstance(line, int) and not isinstance(line, bool) and line > 0
        for line in suspect_lines
    ):
        raise ValueError("LLM suspect_lines must contain positive integers")
    return Diagnosis(cause, confidence, evidence, suspect_lines)


def _diagnosis_schema() -> ResponseTextConfigParam:
    return {
        "format": {
            "type": "json_schema",
            "name": "flaky_test_diagnosis",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cause": {
                        "type": "string",
                        "enum": [
                            cause.value for cause in Cause if cause is not Cause.UNKNOWN
                        ],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "suspect_lines": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                "required": ["cause", "confidence", "evidence", "suspect_lines"],
            },
        },
    }


def _diagnosis_context(
    report: FailureReport, result: ReproResult, source: str, heuristic: Diagnosis
) -> str:
    return (
        f"Failed test: {report.test_id}\nError: {report.error_message}\n"
        f"Stack trace:\n{report.stack_trace}\n\n"
        f"Reproduction matrix: {json.dumps(result.matrix)}\n"
        f"Sample failures: {json.dumps(result.sample_failures)}\n"
        f"Heuristic assessment: {heuristic.cause.value} ({heuristic.confidence})\n"
        f"Heuristic evidence: {json.dumps(heuristic.evidence)}\n\n"
        f"Test source:\n{source}"
    )


def _review_context(
    report: FailureReport,
    repro: ReproResult,
    diagnosis: Diagnosis,
    proposal: FixProposal,
) -> str:
    return (
        f"Test: {report.test_id}\nCause: {diagnosis.cause.value}\n"
        f"Evidence: {json.dumps(diagnosis.evidence)}\n"
        f"Failure rates before: {json.dumps(repro.matrix)}\n"
        f"Failure rates after: {json.dumps(proposal.validation_matrix)}\n"
        f"Applied fix: {proposal.explanation_md}\n"
    )
