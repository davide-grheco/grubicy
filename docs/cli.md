# CLI

All commands run through `uv run grubicy ...` (or `grubicy` if installed in
your environment). Unless noted, `--project` defaults to the current directory or
initializes a new signac project there.

## validate
Validate a config file and its dependency graph.
```bash
uv run grubicy validate pipeline.toml
```

## materialize
Create jobs for every experiment in the spec. Adds `action` and parent ids to the
state point and writes parent metadata to `deps_meta` in the job document.
```bash
uv run grubicy materialize pipeline.toml --project .
uv run grubicy materialize pipeline.toml --project . --dry-run   # compute ids only
```

## render-row
Generate a row `workflow.toml` from the spec. Uses `runner` if provided per action,
otherwise falls back to `python actions/{name}.py {directory}`.
```bash
uv run grubicy render-row pipeline.toml --output workflow.toml
```

## prepare
Convenience wrapper: validate + materialize + render-row (unless `--no-render`).
```bash
uv run grubicy prepare pipeline.toml --project . --output workflow.toml
```

## status
Summarize how many jobs exist per action and how many are missing declared products.
```bash
uv run grubicy status pipeline.toml --project .
uv run grubicy status pipeline.toml --project . --missing-only
```

## collect-params
Flatten parameters (and optional doc fields) across the parent chain for the target
action. Useful for analysis notebooks or exports.
```bash
uv run grubicy collect-params pipeline.toml s3 --project . --format csv
uv run grubicy collect-params pipeline.toml s3 --include-doc --format json
```

## migrate-plan
Plan a migration for one action by transforming its state points. Common use: add
defaults with `--setdefault key=value`. Writes a plan under `.pipeline_migrations/`.
```bash
uv run grubicy migrate-plan pipeline.toml s1 --project . --setdefault b=0
```

Notes:

- Collision strategy is a safety check. With the currently supported CLI migration
  transform (`--setdefault`, which only adds new keys), collisions are not expected.
- If `config` is TOML, `migrate-plan` also updates the config by adding the defaulted
  keys to the action's `sp_keys` and to existing experiment blocks for that action.
  For non-TOML configs, update the spec manually.

## migrate-apply
Execute a migration plan and cascade parent pointer rewrites downstream. Respects
the latest plan unless `--plan` is provided; can resume if interrupted.
```bash
uv run grubicy migrate-apply pipeline.toml s1 --project .
uv run grubicy migrate-apply pipeline.toml s1 --project . --plan path/to/plan.json
uv run grubicy migrate-apply pipeline.toml s1 --project . --dry-run
```

Notes:

- Default plan selection: if `--plan` is not provided, grubicy uses the latest
  `.pipeline_migrations/plan_*.json` in the project.
- `--dry-run` prints the plan JSON and does not modify the workspace.
- Resume: apply writes progress under `.pipeline_migrations/run_<action>_<stamp>/` and
  resumes by default. Use `--no-resume` to start fresh.

See `migrations.md` for a worked example.
