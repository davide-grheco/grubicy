"""Context binding of a workflow spec to a signac project."""

from __future__ import annotations

import signac

from .materialize import MaterializationReport, materialize
from .spec import WorkflowSpec


class WorkflowContext:
    """A validated workflow spec bound to a signac project."""

    def __init__(self, spec: WorkflowSpec, project: signac.Project):
        self.spec = spec
        self.project = project

    def materialize(
        self, experiments=None, dry_run: bool = False
    ) -> MaterializationReport:
        """Create jobs for the provided experiments (or those in the spec)."""

        experiments = self.spec.experiments if experiments is None else experiments
        return materialize(
            self.spec, self.project, experiments=experiments, dry_run=dry_run
        )
