import os
from pathlib import Path

import signac
from signac_deps import WorkflowContext, load_spec, render_row_workflow


def main() -> None:
    root = Path(__file__).resolve().parent
    os.chdir(root)

    spec = load_spec(root / "pipeline.toml")

    project = signac.init_project("library-example")

    ctx = WorkflowContext(spec, project)
    report = ctx.materialize()

    print(f"Materialized {report.total} jobs ({report.created} new)")

    workflow_path = render_row_workflow(spec, root / "workflow.toml")
    print(f"Wrote row workflow: {workflow_path}")


if __name__ == "__main__":
    main()
