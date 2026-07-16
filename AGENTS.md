# AGENTS.md — Flaky Test Detective

## Project Overview

Flaky Test Detective is an agent that ingests CI failure logs from GitHub
Actions, reproduces flaky tests locally under controlled perturbation,
classifies the root cause (race condition, time dependency, shared state,
test-order dependency), generates a minimal fix with a human-readable
explanation, and opens a pull request.

Demo arc: red pipeline in → green PR out.

For pipeline rationale, see `DESIGN.md`. For current priorities, see `TODO.md`.
For past architectural decisions, see `DECISIONS.md`.

## Agent Behavior

For any non-trivial task:

1. Read the relevant modules before proposing changes.
2. Search for existing implementations before adding new code.
3. Explain the implementation plan before editing.
4. Keep changes minimal and scoped to the requested task.
5. Do not refactor unrelated code.
6. If requirements are ambiguous, explain the ambiguity before coding.
7. State any assumptions explicitly.

## Tech Stack

- Python 3.14 (managed via `uv`; pinned in `.python-version`)
- uv for dependency management, virtualenvs, and script running
- pytest (test runner for both the detective and the fixture repos)
- httpx (GitHub API client)
- ruff (lint + format)
- ty (type checking)

## Architecture

ALL implementation code lives under `src/detective/`. Never create modules at
the repo root or in a top-level `detective/` folder.

```
src/detective/
├── ingest/        # Fetch failed CI runs, parse GitHub Actions logs & JUnit XML
├── repro/         # Rerun suspect tests N times in isolation with perturbation
├── classify/      # Label the failure cause: heuristics first, LLM fallback
├── fix/           # Generate a minimal patch + plain-English explanation
├── pr/            # Branch, commit, open the PR via GitHub API
└── cli.py         # Entry point: `uv run detective <command>`
```

- `tests/` contains tests for the detective itself, mirroring `src/detective/`
  structure (e.g. `src/detective/repro/runner.py` → `tests/repro/test_runner.py`).
- `fixtures/flaky-repo/` is a deliberately flaky sample project used as demo
  material and end-to-end test cases. It is NOT app code. Never "fix" fixture
  tests directly — the detective must fix them at runtime in a temp copy.

## Commands

```
uv sync                        # install all deps (dev included)
uv run pytest -q               # run the detective's own test suite
uv run ruff check .            # lint
uv run ruff format --check .   # format check
uv run ty check src/           # type check
uv run detective run --fixture race   # end-to-end run on one fixture
make demo                      # full red→green demo on all fixtures
```

Never use `pip`, `pip install`, `python -m venv`, or bare `python`. Always go
through `uv run` / `uv sync` / `uv add`. To add a dependency:
`uv add <package>` (or `uv add --dev <package>` for dev tooling).

## Coding Standards

Before creating any new function, class, or module:

- Search the repository for similar functionality.
- Reuse existing code when practical.
- Avoid duplicate implementations.
- Python 3.14 syntax throughout. Type hints on all public functions.
  No `from __future__ import annotations` (unnecessary on 3.14).
- Prefer `pathlib.Path` over `os.path`; prefer `subprocess.run` with explicit
  args over shell strings.
- Each pipeline stage exposes one public entry function and communicates via
  the dataclasses in `src/detective/models.py` (`FailureReport`, `ReproResult`,
  `Diagnosis`, `FixProposal`). Do not pass raw dicts between stages.
- Keep functions under ~50 lines. Keep diffs small: one coherent change per task.
- No network calls in unit tests; use recorded fixtures under `tests/data/`.


## Constraints

- Never modify files under `fixtures/` when implementing detective features.
  Detective runs must copy the fixture to a temp dir and patch the copy.
- Never commit secrets. The GitHub token comes from the `GITHUB_TOKEN` env var;
  reference the variable name only, never a value.
- Do not add production dependencies without noting it in the task summary.
- Generated fix PRs must contain exactly one flaky-test fix each.
- Do not edit or delete tests in `tests/` to make them pass; fix the code.

## Never

- Never modify files under `fixtures/`.
- Never edit tests to make them pass.
- Never bypass `uv`.
- Never commit secrets.
- Never introduce new top-level packages.
- Never replace deterministic heuristics with an LLM when heuristics are sufficient.

## Testing & Definition of Done

A task is done only when ALL of the following pass:

1. `uv run pytest -q` — full suite green
2. `uv run ruff check .` and `uv run ruff format --check .` — clean
3. `uv run ty check src/` — no type errors
4. If the task touches the pipeline end-to-end:
   `uv run detective run --fixture race` completes with a green rerun

Run these before declaring any task complete. If the same mistake happens
twice, propose an update to this file with the corrected rule.

## Commit Convention (gitmoji)

Every commit message starts with a gitmoji shortcode, then an imperative
summary (≤72 chars), e.g. `:sparkles: Add JUnit XML parser for failure reports`.
Always use the `:shortcode:` form, never the raw emoji character.

Use this subset (prefer these; consult https://gitmoji.dev only if none fit):

| Shortcode | Use for |
|-----------|---------|
| `:tada:` | Initial project scaffolding |
| `:sparkles:` | New feature (pipeline stage, CLI command, strategy) |
| `:bug:` | Bug fix in the detective itself |
| `:test_tube:` | Add/update a planted flaky fixture test |
| `:white_check_mark:` | Add/update tests for the detective (`tests/`) |
| `:recycle:` | Refactor without behavior change |
| `:memo:` | Docs (README, AGENTS.md, DESIGN.md, DECISIONS.md, TODO.md) |
| `:wrench:` | Config (pyproject.toml, Makefile, ruff/ty settings) |
| `:construction_worker:` | CI workflow changes |
| `:heavy_plus_sign:` / `:heavy_minus_sign:` | Add / remove a dependency (`uv add` / `uv remove`) |
| `:rotating_light:` | Fix lint/type warnings |
| `:zap:` | Performance (e.g. faster repro runs) |
| `:construction:` | Work in progress (avoid on main) |

Rules:
- One gitmoji per commit; pick the dominant intent.
- `:test_tube:` is reserved for fixture flakes; detective code fixes use `:bug:`.
- PRs generated BY the detective (`src/detective/pr/`) title their commits
  with `:adhesive_bandage:` (`:adhesive_bandage: Fix flaky test <test_id>: <cause>`),
  so detective-authored fixes are visually distinct from human/agent commits
  in this repo.

## Workflow Notes

- For any non-trivial task, read the relevant module(s) and propose a short
  plan before editing.
- One task = one coherent outcome (e.g. "implement the JUnit parser"), not
  the whole project.
- Update `TODO.md` checkboxes when a task is completed.
- Record any new architectural decision as an ADR entry in `DECISIONS.md`.