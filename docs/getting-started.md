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
deps = { action = "s2", sp_key = "parent_action" }
outputs = ["s3/out.json"]

[[experiment]]
  [experiment.s1]
  p1 = 1
  [experiment.s2]
  p2 = 10
  test = true
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

## 1a) Define multiple experiments

In grubicy, an "experiment" is one parameter block that can provide values for one or
more actions. To define multiple experiments, repeat the block.

In TOML, that means repeating `[[experiment]]`:
```toml
[[experiment]]
  [experiment.s1]
  p1 = 1
  [experiment.s2]
  p2 = 10
  test = true
  [experiment.s3]
  p3 = 0.1

[[experiment]]
  [experiment.s1]
  p1 = 1
  [experiment.s2]
  p2 = 20
  test = true
  [experiment.s3]
  p3 = 0.1
```

Notes:

- Experiments can omit actions. If an experiment does not specify parameters for a
  given action, grubicy treats that action's parameter block as empty for that
  experiment.
- Parameter reuse is how you get caching across experiments: if two experiments have
  the same parameters for an upstream action (and thus the same identity), they will
  share the same upstream job.
- Config key name: TOML uses `[[experiment]]` (singular table name). YAML/JSON configs
  typically use `experiments:` (plural). grubicy accepts both `experiment` and
  `experiments` at the top level.

## 1b) Using grids

Writing out every combination of parameters by hand gets tedious fast. A **grid**
defines a reusable parameter base — a set of action params that get crossed with every
experiment you add.

### Defining grids

Within a `[[grid]]` block, **list-valued keys are swept** (Cartesian product within
the action) and **scalar keys are fixed**. Combinations across actions are also crossed:

```toml
[[grid]]
name = "main"
  [grid.s1]
  p1 = [1, 2]      # swept: 2 values

  [grid.s2]
  p2 = [10, 20]    # swept: 2 values
  seed = 42        # fixed: appears in all generated combos
```

Multiple `[[grid]]` blocks are independent. Their expansions are **concatenated** into
the grid space (not crossed with each other). Use this to express dependent groups:

```toml
[[grid]]
name = "low"
  [grid.s1]
  p1 = [1]
  [grid.s2]
  p2 = [1, 2, 3, 4]

[[grid]]
name = "high"
  [grid.s1]
  p1 = [2]
  [grid.s2]
  p2 = [5, 6, 7, 8]
```

### Crossing grids with experiments

Experiments define variations that get **crossed against the grid space**. The total
number of jobs is `grid_combos × experiments`:

```toml
# 8 grid combos (4 from "low", 4 from "high")

[[experiment]]                        # crossed with all 8 combos → 8 jobs
  [experiment.s3]
  p3 = 0.1

[[experiment]]                        # crossed with all 8 combos → 8 more jobs
  [experiment.s3]
  p3 = 0.2
```

Each resulting job merges grid params (s1, s2) with experiment params (s3). If an
experiment defines a key also present in the grid, the experiment value takes
precedence.

### Selecting which grids an experiment applies to

By default an experiment is crossed with **all** defined grids. Add a `grids` key to
select only specific ones by name:

```toml
[[experiment]]                         # uses both "low" and "high" → 8 jobs
  [experiment.s3]
  p3 = 0.1

[[experiment]]                         # uses only "low" → 4 jobs
grids = ["low"]
  [experiment.s3]
  p3 = 0.2

[[experiment]]                         # standalone: no grids applied → 1 job
grids = []
  [experiment.s1]
  p1 = 99
  [experiment.s3]
  p3 = 0.5
```

A full runnable example lives in `examples/grid-example/`.

## 1c) Minimal action scripts
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
grubicy prepare
```

This auto-detects `pipeline.toml`, validates the config, creates jobs in topological
order, stores parent ids under `parent_action`, and writes `workflow.toml` for row.
Use `--no-render` to skip the workflow file, or call `grubicy materialize` directly
to only create jobs.

You can always pass an explicit path if needed:
```bash
grubicy prepare pipeline.toml --output workflow.toml
```

## 3) Run actions with grubicy submit (preferred) or row
Submit only ready directories (parents complete, row-eligible, not
completed/submitted/waiting):
```bash
grubicy submit
grubicy submit --action s2   # narrow to one action
```

Or hand everything to row directly:
```bash
row submit
```

To override the command for a specific action, set
`runner = "python actions/custom.py {directory}"` in the spec before rendering.

## 4) Collect parameters and docs
Flatten params across the dependency chain (here, for leaf `s3` jobs):
```bash
grubicy collect-params s3 --format csv > results.csv
```

`collect-params` takes the action name as a positional argument; config is
auto-detected. Add `--include-doc` to bring along non-reserved document fields.
For JSON output, drop `--format` or set `--format json`.

## 5) Migrate when the schema changes
Add a default state point key and cascade parent pointers safely:
```bash
grubicy migrate-plan s1 --setdefault b=0
grubicy migrate-apply s1
```

`migrate-plan` and `migrate-apply` take the action name as a positional argument;
config is auto-detected.  Plans are written under `.pipeline_migrations/` and
execution logs progress so reruns can resume.

For a complete worked example (including collisions and resume behavior), see
[Migrations](migrations.md).

## Example walk-through
`examples/library-example` contains the same three-stage pipeline expressed with
grubicy. Run `grubicy prepare` from that directory to see materialization, row
execution, and result collection end-to-end.

## Typed parameters

grubicy ships an opt-in runtime helper, `grubicy.typed`, that maps state point
values to validated Pydantic v2 models instead of raw dicts. It is entirely
runtime-only.

Three calling styles are supported by `load_action_params`:

```python
from grubicy.typed import WorkflowBindings, load_action_params
from pydantic import BaseModel

class TrainParams(BaseModel):
    lr: float
    n_iter: int
    alpha: float

# 1) Explicit action + registry (original API)
bindings = WorkflowBindings().bind("train", TrainParams)
params = load_action_params(job, "train", bindings)

# 2) Registry only — action inferred from job.sp["action"]
params = load_action_params(job, bindings)

# 3) Direct model class — no registry needed, action inferred
params = load_action_params(job, TrainParams)
```

Notes:
- If the action cannot be inferred (no `action` key in the state point), an
  `ActionParamsNotFoundError` is raised.
- Validation errors are wrapped in `TypedParamsValidationError` with field-prefixed
  messages (e.g., `train.lr: Input should be greater than 0`).
- Reserved state point keys (`action`, `parent_action`) are stripped before
  validation so they never leak into your models.

Advanced usage shown in `examples/typed-params/actions/train.py`:
- You can split one action across multiple models and load them separately from the
  same job (e.g., `TrainOptimParams`, `TrainRegularisationParams`).
- You can load a parent action's params by opening the parent job (via
  `get_parent(job)`) and passing a model class directly: `load_action_params(parent, PrepareParams)`.

See `examples/typed-params/` for a full, runnable demonstration that uses the inferred
registry form, direct model-class form, and parent param loading.
