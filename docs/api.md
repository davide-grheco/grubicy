# API Reference

The library exposes a small surface for working with specs, jobs, and migrations.

## Load and inspect a spec
```python
from pathlib import Path
from signac_deps import WorkflowSpec, load_spec

spec = load_spec("pipeline.toml")
print([a.name for a in spec.topological_actions()])
print(spec.experiments)
```

## Materialize jobs in Python
```python
import signac
from signac_deps import materialize

project = signac.get_project()
report = materialize(spec, project, spec.experiments)
print(report.per_action, report.created)
```

## Resolve parents and files
```python
from signac_deps import get_parent, parent_file, parent_product_exists

child = next(project.find_jobs({"action": "s2"}))
parent = get_parent(child)              # raises if missing
path = parent_file(child, "s1/out.json")
exists = parent_product_exists(child, "s1/out.json")
```

## Render a row workflow
```python
from signac_deps import render_row_workflow

render_row_workflow(spec, "workflow.toml")
```

## Collect parameters across parents
```python
from signac_deps import collect_params_with_parents

rows = collect_params_with_parents(spec, project, "s3", include_doc=True)
table = [r.data for r in rows]
```

## Plan and execute migrations
```python
from signac_deps import plan_migration, execute_migration

def add_default(sp):
    sp = dict(sp)
    sp.setdefault("b", 0)
    return sp

plan = plan_migration(spec, project, "s1", add_default)
report = execute_migration(spec, project, plan)
print(report.updated_actions)
```

See `signac_deps/__init__.py` for the full list of exported helpers.
