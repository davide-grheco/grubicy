Grid example (sweep-example)
============================

This example demonstrates the grid feature: a **named grid** defines a reusable
parameter base, and each `[[experiment]]` block is crossed against it.

## Pipeline structure

```
s1 (p1) → s2 (p2) → s3 (p3)
```

## Parameter space

Two named grids express a dependent p1/p2 relationship:

| grid | p1 | p2           | combos |
|------|----|--------------|--------|
| low  | 1  | 1, 2, 3, 4   | 4      |
| high | 2  | 5, 6, 7, 8   | 4      |

Four experiments vary p3 and optionally restrict which grids they apply to:

| experiment | grids applied  | p3  | jobs generated |
|------------|----------------|-----|----------------|
| A          | all (8 combos) | 0.1 | 8              |
| B          | all (8 combos) | 0.2 | 8              |
| C          | "low" only (4) | 0.3 | 4              |
| D          | none (standalone) | 0.0 | 1           |

**Total s3 jobs: 21** (plus the shared s1/s2 upstream jobs).

## Running

```bash
# 1) Materialize jobs
uv run grubicy prepare pipeline.toml

# 2) Submit ready actions (or use row directly)
grubicy submit pipeline.toml --dry-run
grubicy submit pipeline.toml

# 3) Collect results
uv run python collect_results.py
```

You should see a 21-row table in the output and a `results_table.csv` file.
