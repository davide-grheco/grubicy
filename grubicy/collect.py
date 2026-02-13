"""Utilities to collect flattened parameters and docs across parent chains."""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

import signac

from .spec import ActionSpec, WorkflowSpec
import msgspec


class CollectedRow(msgspec.Struct):
    """A flattened view of a job and its ancestor parameters/docs."""

    data: Dict[str, object]


_RESERVED_DOC_KEYS = {"deps_meta", "pipeline", "pipeline_meta"}


class ParamCollector:
    """Collect flattened parameter/doc rows for a target action."""

    def __init__(
        self,
        spec: WorkflowSpec,
        project: signac.Project,
        *,
        include_doc: bool,
        missing_ok: bool,
    ) -> None:
        self.spec = spec
        self.project = project
        self.include_doc = include_doc
        self.missing_ok = missing_ok
        self._action_map: Dict[str, ActionSpec] = {a.name: a for a in spec.actions}

    def collect(self, target_action: str) -> List[CollectedRow]:
        chain = self._action_chain(target_action)
        rows: List[CollectedRow] = []

        for leaf in self.project.find_jobs({"action": target_action}):
            job_map = self._resolve_parents(chain, leaf)
            if job_map is None:
                if self.missing_ok:
                    continue
                raise LookupError(
                    f"Missing parent for job {leaf.id} when collecting {target_action}"
                )

            flattened = self._flatten_row(chain, job_map)
            rows.append(CollectedRow(data=flattened))

        return rows

    def _action_chain(self, action_name: str) -> Sequence[str]:
        names: List[str] = []
        current = action_name
        while current:
            names.append(current)
            action = self._action_map[current]
            if action.dependency is None:
                break
            current = action.dependency.action
        return list(reversed(names))

    def _resolve_parents(
        self, chain: Sequence[str], leaf: signac.Job
    ) -> Dict[str, signac.Job] | None:
        job_map: Dict[str, signac.Job] = {chain[-1]: leaf}

        for idx in range(len(chain) - 1, 0, -1):
            child_name = chain[idx]
            parent_name = chain[idx - 1]
            child_spec = self._action_map[child_name]
            dep_key = (
                child_spec.dependency.sp_key
                if child_spec.dependency
                else "parent_action"
            )
            child_job = job_map[child_name]
            parent_id = child_job.sp.get(dep_key)
            if parent_id is None:
                return None
            try:
                parent_job = self.project.open_job(id=str(parent_id))
            except LookupError:
                return None
            job_map[parent_name] = parent_job

        return job_map

    def _flatten_row(
        self, chain: Sequence[str], job_map: Mapping[str, signac.Job]
    ) -> Dict[str, object]:
        row: Dict[str, object] = {}

        for name in chain:
            part = job_map[name]
            action_spec = self._action_map[name]
            for key in action_spec.sp_keys:
                if key in part.sp:
                    row[f"{name}.{key}"] = part.sp[key]
            if self.include_doc:
                for dkey, dval in part.doc.items():
                    if dkey in _RESERVED_DOC_KEYS:
                        continue
                    row[f"{name}.doc.{dkey}"] = dval

        return row


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

    collector = ParamCollector(
        spec=spec, project=project, include_doc=include_doc, missing_ok=missing_ok
    )
    return collector.collect(target_action)
