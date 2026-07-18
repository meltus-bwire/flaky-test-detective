# DECISIONS.md — Architectural Decision Records

Append-only. One ADR per decision. Never delete an ADR — supersede it with a
new one and cross-reference. Agents: consult this file before proposing a
change that reverses any decision below; if reversal is justified, add a new
ADR explaining why.

Format:

```
# ADR-NNN: Title
Date · Status (Accepted | Superseded by ADR-XXX)
Decision, Reason, Consequences
```

---

# ADR-001: uv for all environment and dependency management

2026-07-16 · Accepted

**Decision:** All installs, runs, and scripts go through `uv` (`uv sync`,
`uv run`, `uv add`). No pip, no manual venvs, no bare `python`.

**Reason:** Single fast tool for team + agents; lockfile (`uv.lock`) keeps
every teammate and every session on identical deps; Python 3.14 pinned
via `.python-version`.

**Consequences:** CI and Makefile must use uv. Fixture repo also runs under
`uv run pytest` in its temp copy.

---

# ADR-002: src layout with a single `detective` package

2026-07-16 · Accepted

**Decision:** All implementation code lives in `src/detective/`; packaging
declares the src layout; the project is installed in editable mode via
`uv sync`.

**Reason:** Prevents accidental imports of the repo root, keeps test
collection clean, and gives agents one unambiguous rule for where code goes.

**Consequences:** `ModuleNotFoundError` means the environment isn't synced —
run `uv sync`, never restructure folders to "fix" imports.

---

# ADR-003: Typed dataclass contracts between pipeline stages

2026-07-16 · Accepted

**Decision:** Stages communicate only via the dataclasses in
`src/detective/models.py` (`FailureReport`, `ReproResult`, `Diagnosis`,
`FixProposal`) and the `Cause` enum. No raw dicts across stage boundaries.

**Reason:** Stages are independently testable and can be built in parallel by
different people/agents without interface drift; `ty` catches contract breaks.

**Consequences:** Changing a contract means updating `models.py` first, then
both sides, in one task.

---

# ADR-004: Reproduction via targeted perturbation matrix, N=20

2026-07-16 · Accepted

**Decision:** The repro stage reruns a suspect test N=20 times under each
perturbation (scheduling jitter, clock shift/freeze, random test order,
fresh-process isolation) and records a (perturbation → failure rate) matrix.

**Reason:** Naive reruns may never trigger the flake; each flake class has a
forcing condition, and the matrix itself becomes the classification signal.
N=20 balances signal quality against demo runtime.

**Consequences:** Repro is the slowest stage; keep fixture tests fast
(<100 ms each). N is a config value, not a constant scattered in code.

---

# ADR-005: Heuristics-first classification, LLM only as fallback

2026-07-16 · Accepted

**Decision:** Classification tries deterministic rules (repro matrix + static
source signals) first; the LLM analyzer runs only when heuristics are
ambiguous, and must return a structured verdict that is validated before use.

**Reason:** The happy-path demo must be deterministic, fast, offline-safe,
and free. An LLM as the sole classifier is a single point of failure on stage.

**Consequences:** Heuristics need per-cause unit tests against the fixtures;
LLM output is never trusted without schema validation.

---

# ADR-006: Fixes are validated against the same perturbation matrix

2026-07-16 · Accepted

**Decision:** A `FixProposal` is accepted only if rerunning the original
perturbation matrix on the patched temp copy yields a 0% failure rate.
No PR is ever opened for an unvalidated fix.

**Reason:** "Prove it with the same weapon that killed it." This is what makes
the green PR trustworthy rather than a plausible-looking guess.

**Consequences:** Fix strategies are tried least-invasive-first; if all fail
validation, the detective reports findings (issue/comment) instead of a PR.

---

# ADR-007: Detective operates on temp copies; fixtures stay flaky forever

2026-07-16 · Accepted

**Decision:** Repro and fix always run in a temporary copy of the target repo.
Files under `fixtures/` are never modified by any task or detective run.

**Reason:** Fixtures are ground-truth experiments and end-to-end regression
tests; "fixing" them destroys the demo and the test suite in one move.

**Consequences:** The runner owns temp-dir lifecycle (create, patch, validate,
clean up). Any diff touching `fixtures/` in a feature PR is an automatic
review rejection.

---

# ADR-008: Scope frozen to pytest + GitHub Actions, one flake per PR

2026-07-16 · Accepted

**Decision:** The scope is Python/pytest projects on GitHub Actions
only. Each generated PR fixes exactly one flaky test.

**Reason:** Every additional runner/CI provider multiplies parsing and repro
work without improving the demo. One-flake PRs keep review trivial and the
stage narration clean.

**Consequences:** No abstraction layers for hypothetical future runners —
write the concrete thing.

---

# ADR-009: OpenAI models guide diagnosis and generated PR explanations

2026-07-18 · Accepted

**Decision:** The OpenAI Responses API is the primary diagnosis path. It receives
the CI evidence, reproduction results, test source, and deterministic heuristic
signals, then returns a schema-validated diagnosis. A second model call writes
the PR explanation in plain language after the candidate patch passes validation.

**Reason:** The detective must understand unfamiliar failures and communicate
clearly with reviewers, rather than only matching a small set of fixture patterns.

**Consequences:** Runs require `OPENAI_API_KEY`. Heuristics and perturbation
validation remain mandatory guardrails; model output alone can never open a PR.
