# TODO.md — Flaky Test Detective

Rule: work top-to-bottom within a priority band. One checkbox = one
task = one coherent outcome. Check the box and note the commit when done.

## Milestone 0 — Skeleton (do first, everything depends on it)

- [x] M0-001 Init project: `uv init`, `.python-version` → 3.14, `pyproject.toml`
      with src layout (`src/detective`), dev deps: pytest, ruff, ty, httpx
- [x] M0-002 Create `src/detective/models.py` with dataclasses:
      `FailureReport`, `ReproResult`, `Diagnosis`, `FixProposal`, `Cause` enum
      (see DESIGN.md for fields)
- [x] M0-003 Create `src/detective/cli.py` with argparse entry point and
      `[project.scripts] detective = "detective.cli:main"`;
      stub subcommands: `ingest`, `repro`, `diagnose`, `fix`, `run`
- [x] M0-004 Makefile with targets: `demo`, `test`, `lint`, `check`
- [x] M0-005 Build `fixtures/flaky-repo/`: minimal pytest project with
      `test_race.py`, `test_time.py`, `test_shared.py` (planted flakes per
      DESIGN.md), plus its own tiny `pyproject.toml`
- [x] M0-006 CI workflow `.github/workflows/ci.yml`: uv setup, lint, ty, pytest

## Milestone 1 — Walking skeleton (end-to-end on ONE fixture, dumb internals OK)

- [x] M1-001 `repro/runner.py`: copy fixture to temp dir, run one test N times via
      `uv run pytest <test_id>` subprocess, collect pass/fail counts
- [x] M1-002 `repro/perturb.py` v1: random test order + fresh-process-per-test only
- [x] M1-003 `classify/heuristics.py` v1: matrix-only rules (e.g. fails under random
      order but not otherwise → SHARED_STATE)
- [x] M1-004 `fix/patcher.py` v1: hardcoded strategy for SHARED_STATE
      (add reset fixture), apply to temp copy, revalidate matrix
- [ ] M1-005 Wire `detective run --fixture shared` through all stages; print
      before/after failure-rate table
- [ ] M1-006 `make demo` runs the above; END-TO-END GREEN ← 🎯 checkpoint: demo-able

## Milestone 2 — Full cause coverage

- [ ] M2-001 `repro/perturb.py` v2: scheduling jitter injection (settrace/monkeypatched
      sleep) to force RACE_CONDITION
- [ ] M2-002 `repro/perturb.py` v3: clock shifting/freezing to force TIME_DEPENDENCY
- [ ] M2-003 `classify/heuristics.py` v2: static source signals (sleep-near-assert,
      M2-004 `datetime.now()` in assertions, module globals, thread usage)
- [ ] M2-005 `fix/patcher.py` v2: strategies for RACE_CONDITION (poll-with-timeout
      helper) and TIME_DEPENDENCY (freeze-time fixture)
- [ ] M2-006 End-to-end green on all three fixtures via `make demo`

## Milestone 3 — Real CI in, real PR out

- [ ] M3-001 `ingest/github_actions.py`: fetch latest failed workflow run + logs for
      a repo via httpx (`GITHUB_TOKEN` env var)
- [ ] M3-002 `ingest/junit_parser.py`: parse JUnit XML → `FailureReport`
- [ ] M3-003 `pr/github_pr.py`: create branch, commit validated diff, open PR with
      generated explanation body (before/after matrix table in Markdown)
- [ ] M3-004 `detective run --repo <owner/name>`: full loop against a real GitHub repo
- [ ] M3-005 Dry-run flag (`--no-pr`) that prints the PR body instead of posting

## Milestone 4 — Documentation

- [ ] M4-001 `classify/llm_analyzer.py`: LLM fallback for UNKNOWN, structured verdict
      with validation
- [ ] M4-001 Pretty terminal output: live rerun progress, failure-rate table, diff view
- [ ] M4-001 Rehearsed demo script in README: trigger red CI on fixture repo →
      run detective → show green PR
- [ ] M4-001 3-minute pitch notes: problem, arc, what's real vs. mocked

## Bugs / Follow-ups

- [ ] (add as discovered)

## Explicitly NOT doing (see DESIGN.md "Out of Scope")

- Non-pytest runners, non-GitHub CI, production-bug fixing, flake dashboards
