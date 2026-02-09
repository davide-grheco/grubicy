# Getting Started

This guide walks through defining a small three-stage workflow, materializing jobs,
running them with row, and collecting results. Commands assume you are in the repo
root; adjust paths as needed.

## Prerequisites
- Python 3.14+
- `uv` installed (for `uv run ...`)
- `row` installed if you want to execute the generated workflow (not bundled here)

Install project dependencies:
```bash
uv sync --extra dev
```

## 1) Define the workflow spec
Create `pipeline.toml` with your actions, dependencies, and experiment parameters:
```toml
[workspace]
value_file = "signac_statepoint.json"

[[actions]]
name = "s1"
sp_keys = ["p1"]
outputs = ["s1/out.json"]

[[actions]]
name = "s2"
sp_keys = ["p2", "test"]
deps = { action = "s1", sp_key = "parent_action" }
outputs = ["s2/out.json"]

[[actions]]
name = "s3"
sp_keys = ["p3"]
deps = { action = "s2" }
outputs = ["s3/out.json"]

[[experiment]]
  [experiment.s1]
  p1 = 1
  [experiment.s2]
  p2 = 10
  test = "6"
  [experiment.s3]
  p3 = 0.1
```

Key ideas:
- Each `actions` entry names the stage, its state point keys, optional dependency, and
  expected outputs.
- `deps.action` points to the parent action; `deps.sp_key` controls which state point
  key will store the parent job id (default `parent_action`).
- `experiments` hold per-action parameters; missing actions are ignored, extras raise
  a validation error during materialization.

## 2) Materialize jobs (and optionally render row)
```bash
uv run grubicy prepare pipeline.toml --project . --output workflow.toml
```

This validates the config, creates jobs in topological order, stores parent ids under
`parent_action`, and writes `workflow.toml` for row. Use `--no-render` to skip the
workflow file, or call `grubicy materialize ...` directly to only create jobs.

## 3) Run actions with row
If you have action scripts under `actions/` that accept the workspace directory, the
generated workflow works with row out of the box:
```bash
row run workflow.toml
```

To override the command per action, set `runner = "python actions/custom.py {directory}"`
in the spec before rendering.

## 4) Collect parameters and docs
Flatten params across the dependency chain (here, for leaf `s3` jobs):
```bash
uv run grubicy collect-params pipeline.toml s3 --format csv > results.csv
```

Add `--include-doc` to bring along non-reserved document fields. For JSON output,
drop `--format` or set `--format json`.

## 5) Migrate when the schema changes
Add a default state point key and cascade parent pointers safely:
```bash
uv run grubicy migrate-plan pipeline.toml s1 --project . --setdefault b=0
uv run grubicy migrate-apply pipeline.toml s1 --project .
```

Plans are written under `.pipeline_migrations/` and execution logs progress so reruns
can resume.

## Example walk-through
`examples/library-example` contains the same three-stage pipeline expressed with
grubicy. Try the sequence above from that directory to see materialization, row
execution, and result collection end-to-end.
