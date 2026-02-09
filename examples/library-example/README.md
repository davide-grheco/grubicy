Library-based example
=====================

This example mirrors the original sample pipeline (s1 -> s2 -> s3) but uses
the `signac-deps` library to define actions, materialize jobs, and render a row
workflow from a single TOML spec.

Run from this directory so the signac project and workspace live here.

1) Materialize jobs and render row workflow:

```bash
uv run python materialize_and_render.py
```

Outputs:
- Jobs for actions s1, s2, s3 with parent pointers in the state points.
- `workflow.toml` for row execution.

2) Execute actions with row (example):

```bash
row run workflow.toml
```

3) Collect results:

```bash
uv run python collect_results.py
```

You should see a 5-row table corresponding to the experiments in
`pipeline.toml` and a `results_table.csv` file.
