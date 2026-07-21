"""Commit validated fixes and open GitHub pull requests."""

import os
from pathlib import Path
import re
import subprocess

import httpx

from detective.ingest.github_actions import API_ROOT, API_VERSION
from detective.models import Diagnosis, FailureReport, FixProposal, ReproResult


def open_pr(
    repository: str,
    repo_path: Path,
    report: FailureReport,
    repro: ReproResult,
    diagnosis: Diagnosis,
    proposal: FixProposal,
    client: httpx.Client | None = None,
    reviewer_explanation: str | None = None,
) -> str:
    """Commit a validated proposal and return the created PR URL."""
    if not proposal.diff.strip():
        raise ValueError("fix proposal has no diff")
    if any(rate > 0 for rate in proposal.validation_matrix.values()):
        raise ValueError("fix proposal did not pass every validation perturbation")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for opening a pull request")
    owner, name = _split_repository(repository)
    branch = f"detective/fix/{_slug(report.test_id)}"
    message = (
        f":adhesive_bandage: Fix flaky test {report.test_id}: {diagnosis.cause.value}"
    )
    _git(repo_path, ["switch", "-c", branch])
    _git(repo_path, ["apply", "--index"], proposal.diff)
    _git(
        repo_path,
        [
            "-c",
            "user.email=flaky-test-detective@users.noreply.github.com",
            "-c",
            "user.name=Flaky Test Detective",
            "commit",
            "-m",
            message,
        ],
    )
    remote = f"https://x-access-token:{token}@github.com/{owner}/{name}.git"
    _git(repo_path, ["push", remote, f"{branch}:{branch}"])

    body = render_pr_body(report, repro, diagnosis, proposal, reviewer_explanation)
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }
    payload = {"title": message, "head": branch, "base": "main", "body": body}
    if client is not None:
        return _create(client, owner, name, headers, payload)
    with httpx.Client(timeout=30.0, follow_redirects=True) as owned_client:
        return _create(owned_client, owner, name, headers, payload)


def _git(repo_path: Path, args: list[str], input_text: str | None = None) -> None:
    subprocess.run(
        ["git", *args], cwd=repo_path, check=True, text=True, input=input_text
    )


def _create(
    client: httpx.Client,
    owner: str,
    name: str,
    headers: dict[str, str],
    payload: dict[str, str],
) -> str:
    response = client.post(
        f"{API_ROOT}/repos/{owner}/{name}/pulls", headers=headers, json=payload
    )
    response.raise_for_status()
    return response.json()["html_url"]


def render_pr_body(
    report: FailureReport,
    repro: ReproResult,
    diagnosis: Diagnosis,
    proposal: FixProposal,
    reviewer_explanation: str | None = None,
) -> str:
    rows = ["| Perturbation | Before | After |", "| --- | ---: | ---: |"]
    for perturbation in repro.matrix:
        rows.append(
            f"| `{perturbation}` | {repro.matrix[perturbation]:.2f} | "
            f"{proposal.validation_matrix.get(perturbation, 0.0):.2f} |"
        )
    evidence = (
        "\n".join(f"- {item}" for item in diagnosis.evidence) or "- None recorded"
    )
    explanation = reviewer_explanation or proposal.explanation_md
    return (
        f"## What this fixes\n`{report.test_id}`\n\n{explanation}\n\n"
        f"## Diagnosis details\nCause: `{diagnosis.cause.value}`\n"
        f"Confidence: {diagnosis.confidence:.2f}\n\n{evidence}\n\n"
        f"## Verification\nThe same conditions that exposed the problem were rerun "
        f"after the change.\n\n{chr(10).join(rows)}"
    )


def _split_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must be in '<owner>/<name>' form")
    return parts[0], parts[1]


def _slug(test_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", test_id).strip("-") or "test"
