"""Parse JUnit XML failure reports."""

from pathlib import Path
import xml.etree.ElementTree as ET

from detective.models import FailureReport


def parse_junit(source: str | Path) -> FailureReport:
    """Parse the first failed JUnit testcase from XML text or a file."""
    root = ET.fromstring(_read_source(source))
    for testcase in root.iter():
        if _local_name(testcase.tag) != "testcase":
            continue
        failure = next(
            (
                child
                for child in testcase
                if _local_name(child.tag) in {"failure", "error"}
            ),
            None,
        )
        if failure is not None:
            return _failure_report(root, testcase, failure)
    raise ValueError("JUnit XML contains no failed testcase")


def _read_source(source: str | Path) -> str:
    if isinstance(source, Path) or not source.lstrip().startswith("<"):
        return Path(source).read_text()
    return source


def _failure_report(
    root: ET.Element, testcase: ET.Element, failure: ET.Element
) -> FailureReport:
    name = testcase.attrib.get("name", "unknown")
    test_id = _test_id(testcase, name)
    message = (
        failure.attrib.get("message") or failure.attrib.get("type") or "test failed"
    )
    stack_trace = (failure.text or "").strip()
    metadata = {key: value for key, value in root.attrib.items()}
    for suite in root.iter():
        if _local_name(suite.tag) == "testsuite" and any(
            candidate is testcase for candidate in suite.iter("testcase")
        ):
            metadata.update(suite.attrib)
            break
    for key in ("file", "line", "classname"):
        if key in testcase.attrib:
            metadata[f"testcase_{key}"] = testcase.attrib[key]
    return FailureReport(test_id, message, stack_trace, metadata)


def _test_id(testcase: ET.Element, name: str) -> str:
    file_name = testcase.attrib.get("file")
    if file_name:
        return f"{file_name}::{name}"
    classname = testcase.attrib.get("classname", "unknown")
    return f"{classname}::{name}"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]
