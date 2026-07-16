"""Fetch failed GitHub Actions runs and their logs."""

from collections.abc import Mapping
import io
import os
from pathlib import PurePosixPath
import zipfile
from typing import Any

import httpx

from detective.models import FailureReport


API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"


def ingest(repository: str, client: httpx.Client | None = None) -> FailureReport:
    """Fetch the latest failed workflow run and return its log evidence."""
    owner, name = _split_repository(repository)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for GitHub Actions ingestion")

    headers = _headers(token)
    if client is not None:
        return _fetch_report(client, owner, name, headers)
    with httpx.Client(timeout=30.0, follow_redirects=True) as owned_client:
        return _fetch_report(owned_client, owner, name, headers)


def _fetch_report(
    client: httpx.Client,
    owner: str,
    repository: str,
    headers: Mapping[str, str],
) -> FailureReport:
    runs_response = client.get(
        f"{API_ROOT}/repos/{owner}/{repository}/actions/runs",
        params={"status": "failure", "per_page": 1},
        headers=headers,
    )
    runs_response.raise_for_status()
    runs = runs_response.json().get("workflow_runs", [])
    if not runs:
        raise RuntimeError(f"No failed workflow runs found for {owner}/{repository}")

    run = runs[0]
    run_id = run["id"]
    logs_response = client.get(
        f"{API_ROOT}/repos/{owner}/{repository}/actions/runs/{run_id}/logs",
        headers=headers,
    )
    logs_response.raise_for_status()
    metadata = _run_metadata(run)
    return FailureReport(
        test_id="unknown",
        error_message=f"Workflow run {run_id} failed",
        stack_trace=_extract_logs(logs_response.content),
        run_metadata=metadata,
    )


def _split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must be in '<owner>/<name>' form")
    return parts[0], parts[1]


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }


def _run_metadata(run: Mapping[str, Any]) -> dict[str, str]:
    keys = ("id", "name", "head_branch", "head_sha", "run_number", "html_url")
    return {key: str(run[key]) for key in keys if key in run}


def _extract_logs(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            logs = []
            for member in archive.infolist():
                if (
                    not member.is_dir()
                    and PurePosixPath(member.filename).suffix == ".txt"
                ):
                    logs.append(archive.read(member).decode("utf-8", errors="replace"))
            return "\n".join(logs)
    except zipfile.BadZipFile:
        return content.decode("utf-8", errors="replace")
