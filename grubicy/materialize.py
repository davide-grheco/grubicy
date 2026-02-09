"""Job materialization from a workflow spec and experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

import signac

from .spec import ConfigValidationError, WorkflowSpec


@dataclass
class MaterializationReport:
    """Summary of materialization results."""

    per_action: Dict[str, List[str]] = field(default_factory=dict)
    created: int = 0
    total: int = 0
    dry_run: bool = False


def _validate_params(
    params: Dict[str, Any], sp_keys: Iterable[str], action_name: str
) -> Dict[str, Any]:
    """Whitelist parameters against ``sp_keys`` and reject extras."""
    sp_key_set = set(sp_keys)
    extras = set(params) - sp_key_set
    if extras:
        raise ConfigValidationError(
            f"Action '{action_name}' received unknown parameter keys: {sorted(extras)}"
        )
    return {k: params[k] for k in sp_keys if k in params}


def materialize(
    spec: WorkflowSpec,
    project: signac.Project,
    experiments: List[Dict[str, Dict[str, Any]]],
    dry_run: bool = False,
) -> MaterializationReport:
    """Create jobs for all actions across all experiments.

    Parameters
    ----------
    spec
        Validated workflow specification.
    project
        signac project to bind jobs to.
    experiments
        List of per-action parameter mappings, typically ``spec.experiments``.
    dry_run
        If True, compute ids without writing to disk or touching docs.

    Returns
    -------
    MaterializationReport
        Counts of created/total jobs and ids grouped by action.

    Raises
    ------
    ConfigValidationError
        If experiments include unknown parameters or are missing required parents.
    """

    report = MaterializationReport(per_action={}, created=0, total=0, dry_run=dry_run)
    action_order = spec.topological_actions()

    for exp_index, experiment in enumerate(experiments):
        parent_jobs: Dict[str, signac.Job] = {}
        for action in action_order:
            params = experiment.get(action.name, {}) or {}
            filtered_params = _validate_params(params, action.sp_keys, action.name)

            statepoint = {"action": action.name, **filtered_params}

            if action.dependency:
                parent_action = action.dependency.action
                if parent_action not in parent_jobs:
                    raise ConfigValidationError(
                        f"Experiment #{exp_index} is missing parameters for parent action '{parent_action}'"
                    )
                parent_job = parent_jobs[parent_action]
                statepoint[action.dependency.sp_key] = parent_job.id
            else:
                parent_job = None

            job = project.open_job(statepoint)
            report.total += 1
            if action.name not in report.per_action:
                report.per_action[action.name] = []
            report.per_action[action.name].append(job.id)

            if dry_run:
                parent_jobs[action.name] = job
                continue

            created = not Path(job.path).exists()
            job.init()

            if parent_job:
                deps_meta = dict(job.doc.get("deps_meta", {}))
                deps_meta[parent_job.sp.get("action", parent_job.id)] = {
                    "job_id": parent_job.id,
                    "statepoint": dict(parent_job.sp),
                }
                job.doc["deps_meta"] = deps_meta

            parent_jobs[action.name] = job
            if created:
                report.created += 1

    return report
