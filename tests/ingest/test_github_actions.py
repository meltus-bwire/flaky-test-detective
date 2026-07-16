from collections.abc import Iterable
import io
from zipfile import ZipFile

import httpx
import pytest

from detective.ingest.github_actions import ingest


def _logs_archive(files: Iterable[tuple[str, str]]) -> bytes:
    content = io.BytesIO()
    with ZipFile(content, "w") as archive:
        for name, text in files:
            archive.writestr(name, text)
    return content.getvalue()


def test_ingest_fetches_latest_failed_run_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _logs_archive([("job.txt", "pytest failed\n"), ("other.txt", "assert x")])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/actions/runs"):
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "id": 123,
                            "name": "CI",
                            "head_branch": "main",
                            "head_sha": "abc123",
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(200, content=archive, request=request)

    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = ingest("octo/repo", client)

    assert report.test_id == "unknown"
    assert report.error_message == "Workflow run 123 failed"
    assert report.stack_trace == "pytest failed\n\nassert x"
    assert report.run_metadata == {
        "id": "123",
        "name": "CI",
        "head_branch": "main",
        "head_sha": "abc123",
    }


def test_ingest_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        ingest("octo/repo")


@pytest.mark.parametrize("repository", ["octo", "octo/repo/extra", "/repo"])
def test_ingest_validates_repository_name(repository: str) -> None:
    with pytest.raises(ValueError, match="owner.*name"):
        ingest(repository)
