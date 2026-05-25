# CLI

All commands run through `uv run grubicy ...` (or `grubicy` if installed in
your environment).

## Config auto-detection

Every command accepts an optional config path.  When omitted, grubicy walks
from the current directory upward looking for `pipeline.toml`, `pipeline.yaml`,
or `pipeline.yml` (in that order of preference) and uses the first match.

```bash
# explicit
grubicy prepare pipeline.toml

# auto-detected — works if pipeline.toml is in CWD or any parent directory
grubicy prepare
```

A clear error is raised if no config is found and none was given.

> **Note for `migrate-plan`, `migrate-apply`, and `collect-params`:** these
> commands already take a required positional argument (`action`), so the config
> is supplied via the `-c / --config` flag rather than as a positional:
>
> ```bash
> grubicy migrate-plan s1 --setdefault b=0
> grubicy migrate-plan s1 -c /other/pipeline.toml --setdefault b=0
> ```

---

## validate
Validate a config file and its dependency graph.
```bash
grubicy validate
grubicy validate pipeline.toml
```

---

## materialize
Create jobs for every experiment in the spec.  Adds `action` and parent ids to
the state point and writes parent metadata to `deps_meta` in the job document.
```bash
grubicy materialize
grubicy materialize pipeline.toml --project /path/to/project --dry-run
```

---

## render-row
Generate a Row `workflow.toml` from the spec.

```bash
grubicy render-row
grubicy render-row pipeline.toml --output workflow.toml
```

The generated file always contains:

- `[workspace]` with the signac value file path.
- `[default.action]` if your pipeline config has a `[row.default.action]` section
  (shared account, setup scripts, default resources — applied to every action).
- One `[[action]]` entry per action in topological order, including:
  - `previous_actions` wired automatically from `deps` so Row gates downstream
    stages on upstream job completion.
  - `[action.resources]` (walltime, threads, GPUs …) if defined on the action.
  - `[action.submit_options.<cluster>]` (account, SBATCH flags …) if defined.
  - `[action.group]` with the `/action == <name>` include filter and optional
    `maximum_size` / `submit_whole`.

### Adding scheduler metadata to `pipeline.toml`

All Row-specific fields are optional.  They live alongside the action definition
and are forwarded verbatim into `workflow.toml`:

```toml
# Shared defaults for every action
[row.default.action.resources]
walltime.per_directory = "01:00:00"
threads_per_process    = 4

[row.default.action.submit_options.mycluster]
account          = "mylab_account"
setup            = "module load python/3.11"
output_file_path = "row_logs"

# Per-action overrides
[[actions]]
name    = "train"
sp_keys = ["lr", "epochs"]
outputs = ["train/model.pt"]

[actions.resources]
walltime.per_directory = "04:00:00"
threads_per_process    = 8

[actions.submit_options.mycluster]
partition = "gpu"
custom    = ["--gres=gpu:1"]

[actions.group]
maximum_size = 1
```

See [HPC / SLURM](hpc.md) for a full end-to-end cluster example.

---

## prepare
Convenience wrapper: validate + materialize + render-row (unless `--no-render`).
```bash
grubicy prepare
grubicy prepare pipeline.toml --output workflow.toml --no-render
```

---

## submit
Submit only directories that are runnable:

- not completed, submitted, or waiting in Row
- parents (if any) are completed in Row
- listed by Row as eligible for the action

```bash
grubicy submit                      # all actions, CWD project
grubicy submit --action s2          # narrow to one action
grubicy submit --limit 5            # cap submissions
grubicy submit --dry-run            # print directories and row command only
grubicy submit pipeline.toml        # explicit config
```

Notes:
- Requires `row` available on PATH.
- `--project` defaults to CWD.
- Dry-run prints the ready directories and the corresponding `row submit` command.

---

## status
Summarize how many jobs exist per action and how many are missing declared
products.
```bash
grubicy status
grubicy status --missing-only
grubicy status -f table
```

---

## collect-params
Flatten parameters (and optional doc fields) across the parent chain for the
target action.  Useful for analysis notebooks or exports.

Config is supplied via `-c / --config` (optional, auto-detected when omitted).

```bash
grubicy collect-params s3
grubicy collect-params s3 --format csv -o results.csv
grubicy collect-params s3 --include-doc --format json
grubicy collect-params s3 -c pipeline.toml --project /path/to/project
```

---

## migrate-plan
Plan a migration for one action by transforming its state points.  Common use:
add defaults with `--setdefault key=value`.  Writes a plan under
`.pipeline_migrations/`.

Config is supplied via `-c / --config` (optional, auto-detected when omitted).

```bash
grubicy migrate-plan s1 --setdefault b=0
grubicy migrate-plan s1 -c pipeline.toml --setdefault b=0 --collision-strategy keep-first
```

Notes:

- Collision strategy is a safety check.  With `--setdefault` (which only adds
  new keys) collisions are not expected.
- If the config is TOML, `migrate-plan` also updates it: the defaulted keys are
  added to the action's `sp_keys` and to existing experiment blocks for that
  action.  For non-TOML configs, update the spec manually.

---

## migrate-apply
Execute a migration plan and cascade parent pointer rewrites downstream.
Respects the latest plan unless `--plan` is given; can resume if interrupted.

Config is supplied via `-c / --config` (optional, auto-detected when omitted).

```bash
grubicy migrate-apply s1
grubicy migrate-apply s1 -c pipeline.toml --plan path/to/plan.json
grubicy migrate-apply s1 --dry-run
grubicy migrate-apply s1 --no-resume
```

Notes:

- Default plan selection: grubicy uses the latest
  `.pipeline_migrations/plan_*.json` in the project when `--plan` is not given.
- `--dry-run` prints the plan JSON without modifying the workspace.
- Resume: apply writes progress under `.pipeline_migrations/run_<action>_<stamp>/`
  and resumes by default.  Use `--no-resume` to start fresh.

See [Migrations](migrations.md) for a worked example.
