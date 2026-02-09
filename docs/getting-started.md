# Getting Started

This guide walks through defining a small three-stage workflow, materializing jobs,
running them with row, and collecting results. Commands assume you are in the repo
root; adjust paths as needed.

## Prerequisites

- Python 3.9+
- `uv` installed (for `uv run ...`)
- `row` installed if you want to execute the generated workflow (not bundled here)

Install project dependencies:
```bash
uv sync
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

## 1b) Minimal action scripts
Place action scripts in `actions/`. They receive the job workspace directory from row.

Root action (no parent):
```python
# actions/s1.py
from pathlib import Path
import json
import signac

def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    p1 = job.sp["p1"]
    out = {"p1": p1, "value": p1 * p1}

    out_path = Path(job.fn("s1/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out), encoding="utf-8")

if __name__ == "__main__":
    import sys
    main(sys.argv[1])
```

Child action (has a parent):
```python
# actions/s2.py
from pathlib import Path
import json
import signac
from grubicy import get_parent, parent_path, parent_product_exists

def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    parent = get_parent(job)
    if not parent_product_exists(job, "s1/out.json"):
        return
    s1_out = json.loads((parent_path(job) / "s1/out.json").read_text())

    p2 = job.sp["p2"]
    out = {"p1": s1_out["p1"], "p2": p2, "value2": s1_out["value"] + p2}

    out_path = Path(job.fn("s2/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out), encoding="utf-8")

if __name__ == "__main__":
    import sys
    main(sys.argv[1])
```

Notes for actions:

- Accept the workspace directory argument and open the job by id (directory name).
- For children, use `grubicy` helpers (`get_parent`, `parent_path`, `parent_product_exists`) to reach upstream outputs safely.
- Write declared outputs under the job workspace so `grubicy status` (and row products) can verify them.

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
