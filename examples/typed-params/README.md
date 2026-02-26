Typed-params example
====================

This example demonstrates `grubicy.typed` — a runtime helper that maps action
configuration values to validated **Pydantic v2 models** instead of raw
state-point dicts.

The pipeline simulates a three-stage ML experiment:

```
prepare  →  train  →  evaluate
```

- **prepare** — generates synthetic statistics from `n_samples`, `noise`, and `seed`.
- **train** — fits a simple model using `lr`, `n_iter`, and `alpha`.
- **evaluate** — applies a `threshold` to the model score and reports accuracy.

Key files
---------

| File | Purpose |
|------|---------|
| `pipeline.toml` | Workflow spec: actions, `sp_keys`, deps, experiments |
| `actions/prepare.py` | Uses `load_action_params(job, bindings)` with a local one-action registry |
| `actions/train.py` | Shows splitting one action into multiple models and loading parent params |
| `actions/evaluate.py` | Uses `load_action_params(job, bindings)` with a local one-action registry |
| `collect_results.py` | Aggregate results across all experiments |

How typed params work
---------------------

Each action loads its own model(s) and calls `load_action_params`, which supports
three calling styles:

```python
# 1) Explicit action + registry
params = load_action_params(job, "train", bindings)

# 2) Registry only — action inferred from job.sp["action"]
params = load_action_params(job, bindings)

# 3) Direct model class — no registry needed, action inferred
params = load_action_params(job, TrainParams)
```

The example shows both patterns:
- `prepare.py` / `evaluate.py` build a tiny one-action `WorkflowBindings` inside the
  script and use form (2).
- `train.py` splits one action into two models (`TrainOptimParams`,
  `TrainRegularisationParams`) and calls form (3) twice to load both from the same
  state point. It also reads the parent action's params via direct model class
  dispatch.

If a required field is missing or a constraint is violated, a clear path-prefixed
error is raised immediately:

```
TypedParamsValidationError: train.lr: Input should be greater than 0
```

Running the example
-------------------

Run all commands from this directory.

**1. Materialise jobs and render the row workflow:**

```bash
grubicy prepare pipeline.toml
```

**2. Submit ready actions wave by wave (grubicy tracks row status and parent completion):**

```bash
grubicy submit pipeline.toml   # repeat until "No ready directories"
```

**3. Collect results:**

```bash
python collect_results.py
```

You should see a table like:

```
 n_samples  noise      lr  n_iter  alpha       loss   score  accuracy passed
----------------------------------------------------------------------------
       200   0.05  0.0020     100  0.010   0.011739  0.9883    0.9883    yes
       200   0.05  0.0200     200  0.010   0.010039  0.9900    0.9900    yes
       500   0.20  0.0200     200  0.100   0.100760  0.8992    0.8992    yes
```

Note: experiments 1 and 2 share the same `prepare` job because their `n_samples`, `noise`, and `seed` are identical — grubicy deduplicates automatically.
