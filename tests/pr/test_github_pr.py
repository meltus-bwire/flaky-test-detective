import httpx
import pytest
import json

from detective.models import Cause, Diagnosis, FailureReport, FixProposal, ReproResult
from detective.pr.github_pr import open_pr


def _inputs() -> tuple[FailureReport, ReproResult, Diagnosis, FixProposal]:
    return (
        FailureReport("tests/test_race.py::test_it", "boom", "trace", {}),
        ReproResult(
            "tests/test_race.py::test_it", {"baseline": 1.0, "jitter": 0.5}, []
        ),
        Diagnosis(Cause.RACE_CONDITION, 0.9, ["intermittent failure"], []),
        FixProposal(
            "diff --git a/x b/x",
            "Use bounded polling.",
            {"baseline": 0.0, "jitter": 0.0},
        ),
    )


def test_open_pr_commits_and_posts_markdown(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    calls: list[tuple[list[str], str | None]] = []

    def fake_run(args, *, cwd, check, text, input=None):
        calls.append((args, input))

    monkeypatch.setattr("detective.pr.github_pr.subprocess.run", fake_run)
    request_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        request_body.update(json.loads(request.read().decode()))
        return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    report, repro, diagnosis, proposal = _inputs()
    url = open_pr("o/r", tmp_path, report, repro, diagnosis, proposal, client)

    assert url.endswith("/pull/1")
    assert calls[0][0] == [
        "git",
        "switch",
        "-c",
        "detective/fix/tests-test_race.py-test_it",
    ]
    assert calls[1][1] == proposal.diff
    assert request_body["title"].startswith(":adhesive_bandage:")
    assert "| `baseline` | 1.00 | 0.00 |" in request_body["body"]
    client.close()


def test_open_pr_rejects_unvalidated_proposal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    report, repro, diagnosis, proposal = _inputs()
    bad = FixProposal(proposal.diff, proposal.explanation_md, {"jitter": 0.1})
    with pytest.raises(ValueError, match="did not pass"):
        open_pr("o/r", tmp_path, report, repro, diagnosis, bad)
