# signac-deps

Lightweight glue on top of signac for pipelines with multiple actions and explicit
dependencies. Describe your workflow once (TOML/YAML), materialize jobs with parent
pointers, render row workflows, and migrate state points safely when the schema
changes.

## What it adds to signac
- A small config schema for actions, experiments, and downstream dependencies.
- Job materialization that stores parent ids and a `deps_meta` breadcrumb in job
  documents.
- A CLI for validation, row workflow rendering, parameter collection, and migration.
- Python helpers for resolving parents, reading parent products, and flattening
  parameter/doc data across the dependency chain.

## When to reach for it
- You run staged experiments (prep -> simulate -> analyze) and want a single source of
  truth for how jobs relate.
- You use row (or similar orchestrators) and prefer an auto-generated workflow file
  over hand-written filters.
- You need to add defaults or reshape state points without orphaning downstream jobs.

If you only ever run independent signac jobs, you likely do not need signac-deps.
