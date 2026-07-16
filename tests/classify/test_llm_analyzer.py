import pytest

from detective.classify.llm_analyzer import parse_verdict
from detective.models import Cause


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
