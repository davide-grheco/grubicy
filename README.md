signac-deps
===========

Small helper library that layers lightweight dependency management on top of signac.
Describe multi-action pipelines in one config, materialize jobs with parent pointers,
render row workflows, and migrate existing workspaces without rewriting job ids by
hand.

Why use it
----------
- Signac projects stay flat, but real pipelines have multiple stages; signac-deps
  encodes parent -> child links and keeps them consistent.
- One TOML/YAML spec drives job creation, row workflow generation, and parameter
  collection, so pipelines are reproducible and reviewable.
- Migration tools rewrite state points and cascade pointer updates when you add
  defaults or change schema.

Use it when you have multi-step experiments (prepare -> simulate -> analyze), need to
hand results downstream, or want row-ready workflows without manual filters.

Quick start
-----------
1) Install (from this repo):
```bash
uv sync --extra dev
```

2) Describe your pipeline (`pipeline.toml`):
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
  [experiment.s3]
  p3 = 0.1
```

3) Materialize jobs (adds `action` and parent ids to each state point) and render a
   row workflow:
```bash
uv run signac-deps prepare pipeline.toml --project . --output workflow.toml
```

4) Run your stages with row (or any runner that reads `workflow.toml`):
```bash
row run workflow.toml
```

5) Collect downstream-ready parameters and docs:
```bash
uv run signac-deps collect-params pipeline.toml s3 --format csv > results.csv
```

Core pieces
-----------
- **Spec**: `actions` list (name, `sp_keys`, optional `deps`, `outputs`, `runner`)
  plus `experiments` array and optional `workspace.value_file`. Supported formats:
  TOML or YAML.
- **Materialization**: creates signac jobs in topological order and writes
  `deps_meta` to child docs so parent info is recorded.
- **Row rendering**: builds `workflow.toml` with include rules per action and either
  your `runner` command or a default `python actions/{name}.py {directory}`.
- **Collection**: `collect-params` flattens parameters (and optional doc fields)
  across the parent chain so you can analyze results without re-walking jobs.
- **Migration**: plan/apply state point migrations with cascading parent pointer
  rewrites and progress logging under `.pipeline_migrations/`.

Examples
--------
- `examples/sample-project`: a plain signac setup with hand-wired parent pointers.
- `examples/library-example`: the same pipeline expressed with signac-deps
  (`pipeline.toml`, CLI materialization, row workflow, and helper-based actions).

See `docs/getting-started.md` for a fuller walkthrough and `docs/cli.md` for the CLI
surface.
