from pathlib import Path

import pytest

from detective.ingest.junit_parser import parse_junit


def test_parse_junit_extracts_failed_test_and_metadata() -> None:
    xml = """
    <testsuites>
      <testsuite name="unit" timestamp="2026-07-16T12:00:00">
        <testcase classname="tests.test_flaky" name="test_race" file="tests/test_flaky.py" line="12">
          <failure type="AssertionError" message="result was empty">traceback\nassert result</failure>
        </testcase>
      </testsuite>
    </testsuites>
    """

    report = parse_junit(xml)

    assert report.test_id == "tests/test_flaky.py::test_race"
    assert report.error_message == "result was empty"
    assert report.stack_trace == "traceback\nassert result"
    assert report.run_metadata == {
        "name": "unit",
        "timestamp": "2026-07-16T12:00:00",
        "testcase_file": "tests/test_flaky.py",
        "testcase_line": "12",
        "testcase_classname": "tests.test_flaky",
    }


def test_parse_junit_accepts_path_and_error_nodes(tmp_path: Path) -> None:
    report_path = tmp_path / "results.xml"
    report_path.write_text(
        '<testsuite><testcase classname="module" name="test_error">'
        '<error type="RuntimeError">boom</error></testcase></testsuite>'
    )

    report = parse_junit(report_path)

    assert report.test_id == "module::test_error"
    assert report.error_message == "RuntimeError"
    assert report.stack_trace == "boom"


def test_parse_junit_rejects_reports_without_failures() -> None:
    with pytest.raises(ValueError, match="no failed testcase"):
        parse_junit('<testsuite><testcase name="test_ok" /></testsuite>')
