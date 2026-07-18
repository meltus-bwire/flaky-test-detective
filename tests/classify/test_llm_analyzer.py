import pytest

from detective.classify.llm_analyzer import (
    analyze,
    explain_for_review,
    load_config,
    parse_verdict,
)
from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult


def test_parse_verdict_validates_structured_response() -> None:
    diagnosis = parse_verdict(
        '{"cause":"order_dependency","confidence":0.8,'
        '"evidence":["order-sensitive"],"suspect_lines":[4]}'
    )
    assert diagnosis.cause is Cause.ORDER_DEPENDENCY


def test_parse_verdict_rejects_unknown_cause() -> None:
    with pytest.raises(ValueError, match="known cause"):
        parse_verdict(
            {"cause": "unknown", "confidence": 0.5, "evidence": [], "suspect_lines": []}
        )


class _Response:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _Responses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _Response:
        self.calls.append(kwargs)
        return _Response(self.output_text)


class _Client:
    def __init__(self, output_text: str) -> None:
        self.responses = _Responses(output_text)


def test_analyze_uses_structured_openai_output() -> None:
    client = _Client(
        '{"cause":"race_condition","confidence":0.9,'
        '"evidence":["jitter fails"],"suspect_lines":[2]}'
    )
    report = FailureReport("tests/test.py::test_case", "empty result", "trace", {})
    result = ReproResult(report.test_id, {"scheduling_jitter": 1.0}, ["failed"])

    diagnosis = analyze(
        report,
        result,
        "assert result",
        Diagnosis(Cause.UNKNOWN, 0, [], []),
        client,  # type: ignore[arg-type]
    )

    assert diagnosis.cause is Cause.RACE_CONDITION
    request = client.responses.calls[0]
    assert request["model"] == "gpt-5-mini"
    assert request["text"] is not None


@pytest.mark.parametrize(
    "output_text, error",
    [
        ("not JSON", "Expecting value"),
        (
            '{"cause":"race_condition","confidence":1.2,'
            '"evidence":[],"suspect_lines":[]}',
            "known cause and valid confidence",
        ),
        (
            '{"cause":"race_condition","confidence":"0.8",'
            '"evidence":[],"suspect_lines":[]}',
            "invalid schema",
        ),
        (
            '{"cause":"race_condition","confidence":0.8,'
            '"evidence":["jitter fails"],"suspect_lines":[true]}',
            "positive integers",
        ),
        (
            '{"cause":"race_condition","confidence":0.8,'
            '"evidence":[],"suspect_lines":[],"extra":"unsupported"}',
            "invalid schema",
        ),
    ],
)
def test_analyze_rejects_invalid_model_verdicts(output_text: str, error: str) -> None:
    report = FailureReport("tests/test.py::test_case", "empty result", "trace", {})
    result = ReproResult(report.test_id, {"scheduling_jitter": 1.0}, ["failed"])

    with pytest.raises(ValueError, match=error):
        analyze(
            report,
            result,
            "assert result",
            Diagnosis(Cause.UNKNOWN, 0, [], []),
            _Client(output_text),  # type: ignore[arg-type]
        )


def test_explain_for_review_returns_plain_model_markdown() -> None:
    client = _Client(
        "The test sometimes checked the result before the worker finished."
    )
    report = FailureReport("tests/test.py::test_case", "empty", "", {})
    repro = ReproResult(report.test_id, {"baseline": 0.5}, [])
    proposal = FixProposal("diff", "Wait for the worker.", {"baseline": 0.0})

    explanation = explain_for_review(
        report,
        repro,
        Diagnosis(Cause.RACE_CONDITION, 0.9, [], []),
        proposal,
        client,  # type: ignore[arg-type]
    )

    assert explanation.startswith("The test sometimes")


@pytest.mark.parametrize("output_text", ["", " \n\t "])
def test_explain_for_review_rejects_empty_model_responses(output_text: str) -> None:
    report = FailureReport("tests/test.py::test_case", "empty", "", {})
    repro = ReproResult(report.test_id, {"baseline": 0.5}, [])
    proposal = FixProposal("diff", "Wait for the worker.", {"baseline": 0.0})

    with pytest.raises(ValueError, match="empty PR explanation"):
        explain_for_review(
            report,
            repro,
            Diagnosis(Cause.RACE_CONDITION, 0.9, [], []),
            proposal,
            _Client(output_text),  # type: ignore[arg-type]
        )


def test_load_config_reads_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[None] = []
    monkeypatch.setattr(
        "detective.classify.llm_analyzer.load_dotenv", lambda: calls.append(None)
    )

    load_config()

    assert calls == [None]
