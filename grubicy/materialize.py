"""Job materialization from a workflow spec and experiments."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

import signac

from .spec import ActionSpec, ConfigValidationError, WorkflowSpec
import msgspec


class MaterializationReport(msgspec.Struct):
    """Summary of materialization results."""

    per_action: Dict[str, List[str]] = msgspec.field(default_factory=dict)
    created: int = 0
    total: int = 0
    dry_run: bool = False


class Materializer:
    """Materialize jobs for a workflow in a readable, stepwise flow."""

    def __init__(
        self,
        spec: WorkflowSpec,
        project: signac.Project,
        dry_run: bool = False,
    ) -> None:
        self.spec = spec
        self.project = project
        self.dry_run = dry_run
        self.report = MaterializationReport(
            per_action={}, created=0, total=0, dry_run=dry_run
        )
        self._action_order = spec.topological_actions()

    def run(
        self, experiments: Iterable[Mapping[str, Mapping[str, object]]]
    ) -> MaterializationReport:
        """Create jobs for all actions across all experiments.

        Parameters
        ----------
        experiments
            List of per-action parameter mappings, typically ``spec.experiments``.

        Returns
        -------
        MaterializationReport
            Counts of created/total jobs and ids grouped by action.

        Raises
        ------
        ConfigValidationError
            If experiments include unknown parameters or are missing required parents.
        """

        for exp_index, experiment in enumerate(experiments):
            self._materialize_experiment(exp_index, experiment)

        return self.report

    def _materialize_experiment(
        self, exp_index: int, experiment: Mapping[str, Mapping[str, object]]
    ) -> None:
        parent_jobs: Dict[str, signac.Job] = {}

        for action in self._action_order:
            params = experiment.get(action.name, {}) or {}
            filtered_params = self._validate_params(params, action.sp_keys, action.name)

            parent_job = self._resolve_parent(action, parent_jobs, exp_index)
            statepoint = self._build_statepoint(action, filtered_params, parent_job)

            job = self.project.open_job(statepoint)
            self._record_job(action.name, job.id)
            if self.dry_run:
                parent_jobs[action.name] = job
                continue

            created = self._init_job(job)
            if parent_job:
                self._write_dependency_metadata(job, parent_job)

            parent_jobs[action.name] = job
            if created:
                self.report.created += 1

    @staticmethod
    def _validate_params(
        params: Mapping[str, object], sp_keys: Iterable[str], action_name: str
    ) -> Dict[str, object]:
        """Whitelist parameters against ``sp_keys`` and reject extras."""

        sp_key_set = set(sp_keys)
        extras = set(params) - sp_key_set
        if extras:
            raise ConfigValidationError(
                f"Action '{action_name}' received unknown parameter keys: {sorted(extras)}"
            )
        return {k: params[k] for k in sp_keys if k in params}

    @staticmethod
    def _build_statepoint(
        action: ActionSpec,
        params: Mapping[str, object],
        parent_job: Optional[signac.Job],
    ) -> Dict[str, object]:
        statepoint = {"action": action.name, **params}
        if action.dependency and parent_job:
            statepoint[action.dependency.sp_key] = parent_job.id
        return statepoint

    @staticmethod
    def _init_job(job: signac.Job) -> bool:
        created = not Path(job.path).exists()
        job.init()
        return created

    @staticmethod
    def _write_dependency_metadata(job: signac.Job, parent_job: signac.Job) -> None:
        deps_meta = dict(job.doc.get("deps_meta", {}))
        deps_meta[parent_job.sp.get("action", parent_job.id)] = {
            "job_id": parent_job.id,
            "statepoint": dict(parent_job.sp),
        }
        job.doc["deps_meta"] = deps_meta

    def _resolve_parent(
        self,
        action: ActionSpec,
        parent_jobs: Dict[str, signac.Job],
        exp_index: int,
    ) -> Optional[signac.Job]:
        if not action.dependency:
            return None

        parent_action = action.dependency.action
        try:
            return parent_jobs[parent_action]
        except KeyError as exc:
            raise ConfigValidationError(
                f"Experiment #{exp_index} is missing parameters for parent action '{parent_action}'"
            ) from exc

    def _record_job(self, action_name: str, job_id: str) -> None:
        self.report.total += 1
        bucket = self.report.per_action.setdefault(action_name, [])
        bucket.append(job_id)


def materialize(
    spec: WorkflowSpec,
    project: signac.Project,
    experiments: Iterable[Mapping[str, Mapping[str, object]]],
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

    materializer = Materializer(spec=spec, project=project, dry_run=dry_run)
    return materializer.run(experiments)
