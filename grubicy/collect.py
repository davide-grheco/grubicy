"""Utilities to collect flattened parameters and docs across parent chains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import signac

from .spec import WorkflowSpec


@dataclass
class CollectedRow:
    """A flattened view of a job and its ancestor parameters/docs."""

    data: Dict[str, object]


_RESERVED_DOC_KEYS = {"deps_meta", "pipeline", "pipeline_meta"}


def _action_chain(spec: WorkflowSpec, action_name: str) -> List[str]:
    names = []
    current = action_name
    action_map = {a.name: a for a in spec.actions}
    while current:
        names.append(current)
        action = action_map[current]
        if action.dependency is None:
            break
        current = action.dependency.action
    return list(reversed(names))


def collect_params_with_parents(
    spec: WorkflowSpec,
    project: signac.Project,
    target_action: str,
    *,
    include_doc: bool = False,
    missing_ok: bool = False,
) -> List[CollectedRow]:
    """Collect rows for jobs of ``target_action`` with flattened parent params/docs.

    Parameters
    ----------
    spec
        Workflow specification (used to derive the dependency chain and sp_keys).
    project
        signac project containing jobs.
    target_action
        Action name whose jobs should be collected.
    include_doc
        If True, include non-reserved document keys for each action as ``<action>.doc.<key>``.
    missing_ok
        If True, skip rows with missing parent jobs; otherwise raise.
    """

    chain = _action_chain(spec, target_action)
    action_map = {a.name: a for a in spec.actions}
    rows: List[CollectedRow] = []

    for leaf in project.find_jobs({"action": target_action}):
        job_map: Dict[str, signac.Job] = {target_action: leaf}
        missing_parent = False

        for idx in range(len(chain) - 1, 0, -1):
            child_name = chain[idx]
            parent_name = chain[idx - 1]
            child_spec = action_map[child_name]
            dep_key = (
                child_spec.dependency.sp_key
                if child_spec.dependency
                else "parent_action"
            )
            child_job = job_map.get(child_name)
            parent_id = child_job.sp.get(dep_key) if child_job else None
            if parent_id is None:
                missing_parent = True
                break
            try:
                parent_job = project.open_job(id=str(parent_id))
            except LookupError:
                missing_parent = True
                break
            job_map[parent_name] = parent_job

        if missing_parent or len(job_map) != len(chain):
            if missing_ok:
                continue
            raise LookupError(
                f"Missing parent for job {leaf.id} when collecting {target_action}"
            )

        row: Dict[str, object] = {}
        for name in chain:
            part = job_map.get(name)
            if part is None:
                continue
            action_spec = action_map[name]
            for key in action_spec.sp_keys:
                if key in part.sp:
                    row[f"{name}.{key}"] = part.sp[key]
            if include_doc:
                for dkey, dval in part.doc.items():
                    if dkey in _RESERVED_DOC_KEYS:
                        continue
                    row[f"{name}.doc.{dkey}"] = dval
        rows.append(CollectedRow(data=row))

    return rows
