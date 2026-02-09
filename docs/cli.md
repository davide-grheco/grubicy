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

## migrate-apply
Execute a migration plan and cascade parent pointer rewrites downstream. Respects
the latest plan unless `--plan` is provided; can resume if interrupted.
```bash
uv run grubicy migrate-apply pipeline.toml s1 --project .
uv run grubicy migrate-apply pipeline.toml s1 --project . --plan path/to/plan.json
uv run grubicy migrate-apply pipeline.toml s1 --project . --dry-run
```
