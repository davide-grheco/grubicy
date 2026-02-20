"""Utilities for interacting with the row CLI and deriving readiness."""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import signac

from grubicy.helpers import DependencyResolutionError, get_parent
from grubicy.spec import WorkflowSpec


class RowCLIError(RuntimeError):
    """Raised when a row command fails."""


def _run_row(cmd: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RowCLIError(
            f"row command failed ({' '.join(cmd)}): {result.stderr or result.stdout}"
        )
    return result


def _list_directories_with_status(
    project_path: Path, status_flag: str, action: str
) -> set[str]:
    cmd = ["row", "show", "directories", status_flag, "--short", "--action", action]
    result = _run_row(cmd, project_path)
    lines = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower() == "no matches.":
            continue
        lines.append(stripped)
    return set(lines)


def _matches_action(name: str, pattern: str | None) -> bool:
    if pattern in (None, "*"):
        return True
    return fnmatch.fnmatch(name, pattern)


@dataclass
class RowStatus:
    completed: set[str]
    submitted: set[str]
    waiting: set[str]
    eligible_by_action: dict[str, set[str]]

    @property
    def blocked(self) -> set[str]:
        return self.completed | self.submitted | self.waiting


def _gather_row_status(project_path: Path, action_names: list[str]) -> RowStatus:
    completed: set[str] = set()
    submitted: set[str] = set()
    waiting: set[str] = set()
    eligible_by_action: dict[str, set[str]] = {}

    for name in action_names:
        completed |= _list_directories_with_status(project_path, "--completed", name)
        submitted |= _list_directories_with_status(project_path, "--submitted", name)
        waiting |= _list_directories_with_status(project_path, "--waiting", name)
        eligible_by_action[name] = _list_directories_with_status(
            project_path, "--eligible", name
        )

    return RowStatus(
        completed=completed,
        submitted=submitted,
        waiting=waiting,
        eligible_by_action=eligible_by_action,
    )


def _job_is_ready(job: signac.Job, action, status: RowStatus) -> bool:
    if job.id in status.blocked:
        return False

    eligible_set = status.eligible_by_action.get(action.name, set())
    if eligible_set and job.id not in eligible_set:
        return False

    dep = action.dependency
    if not dep:
        return True

    try:
        parent_job = get_parent(job)
    except DependencyResolutionError:
        return False
    return parent_job.id in status.completed


def ready_directories(
    spec: WorkflowSpec,
    project: signac.Project,
    action_pattern: str | None = None,
) -> list[str]:
    """Compute ready directories based on row status, eligibility, and dependencies.

    A directory is ready when it is not completed/submitted/waiting, all parents (if
    any) are completed, and (when row reports eligible dirs for the action) it appears
    in that eligible list.
    """

    project_path = Path(project.path)

    action_names = [a.name for a in spec.actions]
    status = _gather_row_status(project_path, action_names)

    ready: list[str] = []
    for action in spec.topological_actions():
        if not _matches_action(action.name, action_pattern):
            continue
        for job in project.find_jobs({"action": action.name}):
            if _job_is_ready(job, action, status):
                ready.append(job.id)

    return ready


def submit_directories(
    project_path: Path,
    directories: Iterable[str],
    action: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Submit the provided directories with row."""

    cmd: list[str] = ["row", "submit", "--yes"]
    if action:
        cmd.extend(["--action", action])
    if dry_run:
        cmd.append("--dry-run")
    if limit is not None:
        cmd.extend(["-n", str(limit)])
    cmd.extend(list(directories))
    _run_row(cmd, project_path)
