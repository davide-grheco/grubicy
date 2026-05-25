# Running on HPC with SLURM (via Row)

grubicy turns your `pipeline.toml` into a `workflow.toml` that
[Row](https://row.readthedocs.io) uses to submit jobs to SLURM (or any other
scheduler).  This page covers the full path from config to running jobs on a
cluster, including a worked example for CESGA FT3.

---

## The two-file model

| File | Purpose | Managed by |
|------|---------|------------|
| `pipeline.toml` | Define actions, parameters, experiments, and scheduler metadata | grubicy |
| `workflow.toml` | Row workflow config — workspace, actions, resources, submit options | **generated** by `grubicy prepare` |

You edit `pipeline.toml`.  `workflow.toml` is regenerated every time you run
`grubicy prepare` and should not be committed or hand-edited.

---

## Quick-start checklist

```bash
# 1. Write / edit pipeline.toml  (see below for the full format)

# 2. Generate the signac workspace and workflow.toml
grubicy prepare                        # auto-detects pipeline.toml

# 3. Check what Row sees
row show status

# 4. Submit a stage (Row handles the SLURM script)
row submit --action prepare
row submit --action train
```

---

## Adding scheduler metadata to `pipeline.toml`

All Row-specific fields live under three optional keys in each `[[actions]]`
entry.  They are forwarded verbatim into `workflow.toml` — grubicy does not
interpret them.

### `resources` — walltime, CPUs, GPUs

```toml
[[actions]]
name = "train"
sp_keys = ["lr", "epochs"]
outputs = ["train/model.pt"]

[actions.resources]
walltime.per_directory = "02:00:00"   # HH:MM:SS per signac job
threads_per_process    = 8            # → #SBATCH --cpus-per-task
# gpus_per_process     = 1           # uncomment for GPU actions
```

Row uses these to build the `#SBATCH` header and to pick the right partition
automatically (if your cluster config defines partition limits).

### `submit_options` — account, modules, extra SBATCH flags

Each key under `submit_options` is a **cluster name** as defined in
`$HOME/.config/row/clusters.toml` (or Row's built-in list):

```toml
[actions.submit_options.ft3]
account          = "mylab_account"
setup            = """
module load miniforge3/24.1.2-0
conda activate myenv
"""
custom           = ["--mem-per-cpu=4000M"]
output_file_path = "row_logs"
output_file_name = "{action_name}-%j.out"
```

### `group` — batch size per SLURM job

```toml
[actions.group]
maximum_size = 4      # run up to 4 signac jobs per SLURM submission
# submit_whole = true # require Row to always submit whole groups
```

If each directory takes ~30 min and you want 2-hour jobs, set
`maximum_size = 4`.

---

## Shared defaults with `[row.default.action]`

Rather than repeating `submit_options` on every action, put shared config
under `[row.default.action]`.  It becomes `[default.action]` in
`workflow.toml` and applies to every action that doesn't override it:

```toml
# pipeline.toml
[row.default.action]
command = "python actions.py --action $ACTION_NAME {directories}"

[row.default.action.resources]
walltime.per_directory = "01:00:00"
threads_per_process    = 4

[row.default.action.submit_options.ft3]
account          = "mylab_account"
setup            = "module load miniforge3/24.1.2-0\nconda activate myenv"
custom           = ["--mem-per-cpu=4000M"]
output_file_path = "row_logs"
output_file_name = "{action_name}-%j.out"
```

Per-action `resources` or `submit_options` override the defaults for that
action only.

---

## Stage gating — `previous_actions`

grubicy automatically writes `previous_actions` into `workflow.toml` based on
your `deps` declarations.  Row uses this to hold back downstream submissions
until upstream jobs have completed their `products`.

```
prepare ──► train ──► eval
```

This means `row submit` for `train` will only include jobs whose `prepare`
products already exist.  You don't need to manage this manually.

---

## Full CESGA FT3 example

Below is a complete `pipeline.toml` for a three-stage ML pipeline running on
CESGA FT3.

```toml
[workspace]
value_file = "signac_statepoint.json"

# -------------------------------------------------------------------
# Row defaults shared by every action
# -------------------------------------------------------------------
[row.default.action]
command = "python actions.py --action $ACTION_NAME {directories}"

[row.default.action.submit_options.ft3]
account          = "mylab_account"
setup            = """
module load miniforge3/24.1.2-0
conda activate myenv
"""
custom           = ["--mem-per-cpu=4000M"]
output_file_path = "row_logs"
output_file_name = "{action_name}-%j.out"

# -------------------------------------------------------------------
# Actions
# -------------------------------------------------------------------

[[actions]]
name    = "prepare"
sp_keys = ["seed", "dataset"]
outputs = ["prepare/features.npy"]

[actions.resources]
walltime.per_directory = "00:30:00"
threads_per_process    = 2

[actions.group]
maximum_size = 8

# ---
[[actions]]
name    = "train"
sp_keys = ["lr", "epochs"]
outputs = ["train/model.pt", "train/metrics.json"]
deps    = { action = "prepare" }

[actions.resources]
walltime.per_directory = "04:00:00"
threads_per_process    = 8

[actions.submit_options.ft3]
# Override default: train needs a dedicated GPU partition
partition = "gpu"
custom    = ["--mem-per-cpu=8000M", "--gres=gpu:1"]

[actions.group]
maximum_size = 1   # each training run gets its own job

# ---
[[actions]]
name    = "eval"
sp_keys = ["threshold"]
outputs = ["eval/report.json"]
deps    = { action = "train" }

[actions.resources]
walltime.per_directory = "00:15:00"
threads_per_process    = 2

[actions.group]
maximum_size = 16

# -------------------------------------------------------------------
# Experiments
# -------------------------------------------------------------------
[[experiment]]
  [experiment.prepare]
  seed    = 42
  dataset = "chembl"

  [experiment.train]
  lr     = 1e-3
  epochs = 50

  [experiment.eval]
  threshold = 0.5

[[experiment]]
  [experiment.prepare]
  seed    = 42
  dataset = "chembl"

  [experiment.train]
  lr     = 5e-4
  epochs = 100

  [experiment.eval]
  threshold = 0.5
```

After `grubicy prepare`, `workflow.toml` will contain:

* `[default.action.submit_options.ft3]` with your shared account/setup
* Three `[[action]]` entries in dependency order (`prepare` → `train` → `eval`)
* `previous_actions = ["prepare"]` on `train`, `previous_actions = ["train"]` on `eval`
* Per-action `resources` and `submit_options` merged with the defaults

Then submit stage by stage:

```bash
row show status                          # inspect what's eligible
row submit --action prepare              # submits up to 8 dirs per job
row submit --action train                # only eligible once prepare products exist
row submit --action eval                 # gated on train products
```

---

## Configuring Row clusters

Row's built-in cluster list covers many national facilities.  For a custom
cluster (or to add CESGA FT3 if it's not built in), create
`$HOME/.config/row/clusters.toml`:

```toml
[[cluster]]
name = "ft3"

[cluster.identify]
# Row auto-detects this cluster when the hostname matches
scheduler = "slurm"

[[cluster.partition]]
name    = "short"
maximum_cpus = 128
maximum_gpus = 0

[[cluster.partition]]
name    = "gpu"
maximum_cpus = 64
maximum_gpus = 8
```

See the [Row cluster documentation](https://row.readthedocs.io/en/stable/clusters/)
for the full schema.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| All actions submitted at once | Missing `deps` in `pipeline.toml` → no `previous_actions` in `workflow.toml` |
| Jobs killed immediately | No `walltime` in `[actions.resources]` |
| Wrong partition selected | Omit `partition` and let Row auto-select, or set it explicitly |
| `workflow.toml` out of date | Re-run `grubicy prepare` after every `pipeline.toml` edit |
| Row can't find the cluster | Check `$HOME/.config/row/clusters.toml`; run `row show clusters` |
