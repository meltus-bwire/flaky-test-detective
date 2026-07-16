# DESIGN.md — Flaky Test Detective

This document explains *why* the system is shaped the way it is. For the
what/where, see `AGENTS.md`. For decision history, see `DECISIONS.md`.

## The Problem

A flaky test passes and fails without code changes. CI logs tell you *that* it
failed, not *why*. Humans debug flakes by rerunning, guessing at causes, and
sprinkling sleeps. The detective automates the disciplined version of that
loop: reproduce deterministically, classify by evidence, fix minimally,
explain clearly.

## Pipeline

```
GitHub Actions failure
        │
        ▼
┌───────────────┐   FailureReport    ┌───────────────┐   ReproResult
│    INGEST     │ ─────────────────► │     REPRO     │ ─────────────┐
│ logs + JUnit  │                    │ N runs +      │              │
│ XML parsing   │                    │ perturbation  │              ▼
└───────────────┘                    └───────────────┘      ┌───────────────┐
                                                            │   CLASSIFY    │
┌───────────────┐   FixProposal     ┌───────────────┐       │ heuristics →  │
│      PR       │ ◄──────────────── │      FIX      │ ◄──── │ LLM fallback  │
│ branch+commit │                   │ patch + expl. │  Diag │               │
└───────────────┘                   └───────────────┘ nosis └───────────────┘
```

Each stage is a pure-ish function over a typed dataclass. This makes every
stage independently testable and lets teammates (or parallel agents) own
stages without merge collisions.

## Stage Interfaces

Each stage exposes one public function:

FailureReport
    ↓
reproduce()
    ↓
ReproResult
    ↓
classify()
    ↓
Diagnosis
    ↓
propose_fix()
    ↓
FixProposal
    ↓
open_pr()

No stage calls another stage directly.
The CLI orchestrates the pipeline.

## Stage Rationale

### 1. Ingest — start from evidence, not source code

We parse two artifacts: the GitHub Actions log (for environment context:
runner OS, parallelism, timing) and JUnit XML (for the precise failing test
id, message, and stack trace). Starting from structured failure evidence
rather than "scan the repo for smells" keeps the search space small and the
demo fast.

Output: `FailureReport(test_id, error_message, stack_trace, run_metadata)`.

### 2. Repro — perturbation is the core trick

A flake that can't be reproduced can't be confidently fixed. Naively rerunning
a flaky test N times is slow and may never trigger the failure. Instead we
rerun under *targeted perturbation*, because each flake class has a forcing
condition:

| Perturbation                     | Forces which flake class        |
|----------------------------------|---------------------------------|
| Thread/async scheduling jitter (random small delays injected via tracing hooks) | Race conditions |
| Frozen/shifted clock (patch `time`/`datetime`, e.g. run "at" 23:59:59, month end, DST boundary) | Time dependency |
| Randomized test order (`pytest -p no:randomly` off/on, `--forked`)  | Shared state, order dependency  |
| Fresh process per test           | Module-level state leakage      |

The runner executes the suspect test N times (default N=20) under each
perturbation in a **temp copy** of the repo, never in place. The matrix of
(perturbation → failure rate) is itself the primary classification signal.

Output: `ReproResult(test_id, matrix: dict[Perturbation, FailureRate], sample_failures)`.

### 3. Classify — heuristics first, LLM as fallback

Two-tier design:

1. **Heuristics (cheap, deterministic, demo-safe):** combine the repro matrix
   with static signals in the test source — `time.sleep(` near assertions,
   `datetime.now()` / `time.time()` in assertions, module-level mutable
   globals, thread/`asyncio.gather` usage without joins, filesystem/tmp reuse.
   If matrix + static signal agree, emit a `Diagnosis` with high confidence.
2. **LLM analyzer (fallback):** only when heuristics are ambiguous. Prompt =
   test source + failure diff + repro matrix. The LLM must return a structured
   verdict (cause enum + confidence + cited evidence lines), which we validate
   before accepting.

Rationale: heuristics make the happy-path demo deterministic and free; the LLM
handles the long tail without being a single point of failure on stage.

Output: `Diagnosis(cause: Cause, confidence, evidence, suspect_lines)`.

`Cause` enum: `RACE_CONDITION | TIME_DEPENDENCY | SHARED_STATE | ORDER_DEPENDENCY | UNKNOWN`.

### 4. Fix — minimal, cause-specific patch templates

Each cause maps to a small family of fix strategies, tried in order of
least-invasive first:

- **Race:** replace sleep-based waits with explicit synchronization
  (event/join/condition), or poll-with-timeout helper.
- **Time:** inject a clock (parameterize `now()`), or freeze time in the test
  via monkeypatch fixture.
- **Shared state:** isolate via fixture-scoped setup/teardown, copy shared
  structures, or reset module state in a fixture.
- **Order dependency:** remove hidden coupling; make the test create its own
  preconditions.

The patch is applied to the temp copy and validated by rerunning the *same
perturbation matrix* that originally triggered the flake — the fix is accepted
only if the failure rate drops to 0 across the matrix. This "prove it with the
same weapon that killed it" loop is what makes the PR trustworthy.

Output: `FixProposal(diff, explanation_md, validation_matrix)`.

### 5. PR — the deliverable is the explanation

The PR body is generated from the `FixProposal`: what was flaky, the evidence
(failure rates before/after per perturbation), the cause in plain English, and
why this fix addresses it. One flake per PR keeps review trivial and makes the
demo narration clean.

## Fixture Strategy (demo design)

`fixtures/flaky-repo/` is a tiny standalone pytest project with planted flakes,
one per cause class:

- `test_race.py` — background thread writes a result; assertion sometimes runs first
- `test_time.py` — asserts on `datetime.now()` formatting; fails near midnight/UTC offset
- `test_shared.py` — two tests mutate a module-level list; fails under random order

Each fixture is a controlled experiment: we know ground truth, so fixtures
double as end-to-end regression tests for the detective and as reproducible
demo scenarios. The detective always operates on a temp copy so fixtures stay
flaky forever.

## Error Handling Philosophy

Every stage can fail; the pipeline degrades gracefully rather than crashing:
- Can't reproduce → open an issue (not a PR) with the repro attempt matrix.
- Classification `UNKNOWN` → open a diagnostic PR comment, no code change.
- Fix fails validation → try next strategy; exhausted → report findings only.

Never open a PR whose fix hasn't passed matrix validation.

## Out of Scope

- Languages other than Python / runners other than pytest
- CI providers other than GitHub Actions
- Fixing production code bugs surfaced by tests (we fix *test* flakiness only)
- Long-term flake tracking / quarantine dashboards