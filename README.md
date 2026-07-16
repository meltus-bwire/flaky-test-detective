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
