grubicy
=======

grubicy is a small helper library + CLI that layers lightweight dependency management
on top of signac.

It is named after Vittore Grubicy de Dragon, an influential promoter of Italian
Divisionism. That movement “divided” light and color into strokes; grubicy does the
same for workflows: it divides a signac project into stages, connects them with
explicit parent -> child links, and keeps those links consistent even as your schema
evolves.

With one TOML/YAML spec you can:
- describe multi-action pipelines in a single file,
- materialize signac jobs with parent pointers stored in state points,
- record full parent state points in docs for traceability (`deps_meta`),
- render row workflows, and
- migrate existing workspaces with cascading pointer updates without doing it by hand.

Why use it
----------

Signac projects are naturally flat, but real computational work is often staged:
- Prepare -> simulate -> analyze
- Preprocess -> train -> evaluate
- Extract -> transform -> aggregate

grubicy helps when you want those stages to be:
- cached and reusable (shared intermediates across experiments),
- explicitly wired (no hidden coupling via shared parameter keys),
- reviewable and reproducible (the pipeline is a spec file),
- maintainable over time (schema changes do not break downstream links).

What you get:
- Explicit dependencies: parent job ids live in the child state point, so “same params
  but different parents” never collide.
- One spec for everything: job creation, row workflow rendering, and parameter
  collection are driven by a single config file.
- Safe migrations: plan/apply state point migrations and automatically cascade
  dependency-pointer rewrites downstream, with progress logging.

When to use it
--------------
- Use grubicy if you have multi-step experiments, pass results downstream between
  stages, or want row-ready workflows without writing manual include filters.
- If your project is truly single-stage, grubicy will feel like extra structure you do
  not need.

Quick start
-----------

1) Install (from this repo)
```bash
uv sync --extra dev
```

2) Describe your pipeline (`pipeline.toml`)
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

Notes:
- Each `[[actions]]` block defines a stage.
- `sp_keys` lists the parameters that define identity for that stage.
- `deps` declares which upstream action this stage depends on. The library writes the
  upstream job id into the dependent job’s state point using `sp_key`.
- Experiments use per-action subsections: parameters do not need to be shared across
  stages.

Defining multiple experiments:
- Repeat the `[[experiment]]` block to create multiple experiment rows. See a complete
  multi-experiment spec in `examples/library-example/pipeline.toml`.

3) Materialize jobs and render a row workflow
```bash
uv run grubicy prepare pipeline.toml --project . --output workflow.toml
```

This will:
- create/open signac jobs in topological order,
- write action and dependency pointers (parent job ids) into each state point,
- store `deps_meta` in job docs (including full parent state points),
- generate `workflow.toml` for row.

4) Run with row (or any runner that reads the workflow)
```bash
row run workflow.toml
```

5) Collect downstream-ready parameters
```bash
uv run grubicy collect-params pipeline.toml s3 --format csv > results.csv
```

This flattens the parameter chain for the `s3` stage (and optionally selected doc
fields), so you can analyze results without manually walking parents.

Core pieces
-----------

Spec
- A spec file contains:
  - `actions`: list of stages with name, `sp_keys`, optional `deps` (parent action +
    `sp_key` used to store parent job id), optional `outputs`, optional `runner`.
  - `experiment`: list of experiments with per-action subsections.
  - optional `workspace.value_file`.
- Supported formats: TOML and YAML.

Materialization
- Creates/opens jobs in topological order and wires dependencies by writing parent job
  ids into the child state point. Also writes `deps_meta` into child job docs so
  parent state points are recorded for traceability and repair.

Row rendering
- Builds `workflow.toml` with per-action include rules, using either your explicit
  `runner` or a default `python actions/{name}.py {directory}`.

Collection
- `collect-params` flattens parameters (and optional document fields) across the
  dependency chain for a target stage.

Migration
- Plan/apply state point migrations with collision detection, cascading parent-pointer
  rewrites downstream, and restartable progress logs under `.pipeline_migrations/`.
- Useful when you add defaults (`setdefault`) or evolve the schema and need downstream
  pointers updated consistently.

Examples
--------
- `examples/sample-project`: a plain signac setup with hand-wired parent pointers.
- `examples/library-example`: the same pipeline expressed with grubicy
  (`pipeline.toml`, CLI materialization, row workflow, and helper-based actions).

Documentation
- `docs/getting-started.md` — walkthrough
- `docs/cli.md` — CLI reference
- `docs/migrations.md` — worked migration example
