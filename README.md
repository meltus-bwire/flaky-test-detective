# Flaky Test Detective

Flaky Test Detective turns a failed GitHub Actions test into a reproducible,
minimal fix and (optionally) a pull request. It targets Python/pytest projects
running on GitHub Actions.

## Setup

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest -q
```

Run the complete local demo against the planted fixtures:

```sh
make demo
```

For a checked-out repository, provide a GitHub token when opening a PR:

```sh
export GITHUB_TOKEN=...
uv run detective run --repo owner/name
uv run detective run --repo owner/name --no-pr  # print the body only
```

## Use cases

- **CI triage:** turn an intermittent pytest failure into evidence about race,
  time, shared-state, or order-dependent behavior.
- **Safe automated repair:** generate a small, cause-specific patch and verify
  it against the same perturbation matrix before opening a PR.
- **Developer investigation:** use `--no-pr` to inspect the diagnosis, failure
  rates, and proposed diff without creating a branch or changing GitHub.
- **Fixture and regression testing:** run `make demo` to exercise the complete
  red-to-green workflow locally with deterministic sample flakes.

## Integrating with an existing project

The least-invasive integration is a scheduled or failure-triggered CI job. Give
the job a checkout, Python/uv, and a token with permission to create branches
and pull requests, then invoke:

```yaml
- uses: actions/checkout@v4
- run: uv sync
- run: uv run detective run --repo ${{ github.repository }}
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Start with `--no-pr` in a reporting job, review the generated body and diff,
then enable PR creation once the repository's test and permission setup is
validated. The detective only targets pytest tests and expects the failed run's
logs to identify a node such as `tests/test_cache.py::test_refresh`.

For custom orchestration, import the typed stage functions instead of invoking
the CLI. Pass a `FailureReport` to `reproduce`, a `ReproResult` to `classify`,
then pass the resulting `Diagnosis` to `propose_fix`; hand the validated
`FixProposal` to `open_pr`. This lets an existing incident bot supply its own
log parser or approval gate while retaining the detective's reproduction and
validation guarantees. All stages communicate through the dataclasses in
`src/detective/models.py`.

Repositories remain untouched during analysis: reproduction and patch
validation use temporary copies. Only the PR stage creates a branch and pushes
the validated diff, and each generated PR contains one flaky-test fix.

## Architecture

The CLI orchestrates typed pipeline stages:

```text
GitHub Actions logs/JUnit
          ↓ FailureReport
       Ingest → Reproduce (N=20, targeted perturbations)
          ↓ ReproResult
       Classify (heuristics, then validated LLM fallback)
          ↓ Diagnosis
       Fix (minimal patch + matrix validation)
          ↓ FixProposal
       PR (branch, commit, explanation, pull request)
```

Implementation lives under `src/detective/`; its stages are `ingest`, `repro`,
`classify`, `fix`, and `pr`. Reproduction and patch validation run in temporary
copies, so the deliberately flaky projects under `fixtures/` remain unchanged.

## Tech stack

- Python 3.14, managed with uv
- pytest for the detective and fixture test suites
- httpx for GitHub API access
- ruff for linting and formatting
- ty for static type checking

See [DESIGN.md](DESIGN.md) for pipeline rationale and [DECISIONS.md](DECISIONS.md)
for architectural decisions.
