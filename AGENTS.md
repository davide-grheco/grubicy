
# agents.md — Signac deps (LLM Contributor Contract)

This file is the **normative contract** for LLM agents (and humans) contributing to this repository.
Follow it exactly unless a maintainer explicitly overrides it in the task request.

---

## 1) Mission

Build a signac-based scaffold that supports:

- **Multiple job types** in a single signac workspace
- **Explicit downstream → upstream** dependency mapping (per job type)


## 2) Tooling & Local Commands (uv + ruff + pytest)

This repo uses **uv** for environment and execution.

### Setup
- `uv sync --extra dev`

### Tests
- `uv run -m pytest`

### Lint / format
Use ruff for both lint and formatting (if configured in the repo):
- `uv run ruff check .`
- `uv run ruff format .`

**Do not use pip/poetry/conda** unless the repo explicitly requires it.


## 3) Coding Standards (Enforced)

- Every new public function/method MUST have a concise docstring:
  - purpose
  - inputs/outputs
  - key behavior constraints (especially gating/atomicity)
- Prefer small, composable functions.
- Keep behavior deterministic (seed when needed).
- Keep text output ASCII unless the repo already uses Unicode widely.
- Avoid adding new heavy dependencies unless clearly justified.
- Code must have a clear documentation

### Public API discipline
If something is labeled “planned” or not already exposed:
- Agents MUST NOT expose new public APIs without an explicit request.
- Internal helpers are fine; new user-facing CLI/API requires tests + docs + examples updates.

## 4) Tests: What to Add (Minimum Coverage)

When you change behavior, add tests and ensure that all tests pass. Try to keep code coverage above 75% at all times, higher is better.

## 5) Documentation & Examples Must Match Reality

If you modify:
- public CLI surface
- defaults behavior
- workflow generation
- dependency semantics
- migration behavior

…then you MUST also update:
- README/docs
- docs/
- example projects (e.g., `examples/minimal_scaffold`)
- any `scaffold.toml` or workflow config artifacts

Examples must run as documented (using `uv run ...`).


## 6) Agent Work Discipline (Required)

Agents MUST use `todo.txt` as an execution plan.

### Format
- One line per step.
- Prefix each line with `[ ]`, `[x]`, or `[!]` (blocked).

Example:
- `[ ] Inspect existing dependency resolution + doc schema`
- `[ ] Add unit test for ambiguity handling`
- `[x] Run pytest`
- `[!] Blocked: missing fixture for temp workspace`

### Rules
- Before coding: write the todo list in order.
- Execute steps in order.
- After each step: mark it `[x]` or `[!]` with a short reason.
- Do not do unplanned work not listed in `todo.txt`.

## 13) When Unsure

If repository reality conflicts with this file:
- Ask if unsure
- prefer existing code conventions **only if** they do not violate the “Hard Guardrails”
- otherwise, align code to this contract (and add tests)

When requirements are unclear, make the safest change:
- small, reversible
- fully tested
- preserves identity semantics
- preserves idempotency and atomicity
