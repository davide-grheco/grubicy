"""Utilities for interacting with the row CLI and deriving readiness."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Iterable, List, Sequence, Set

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
) -> Set[str]:
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


def ready_directories(
    spec: WorkflowSpec,
    project: signac.Project,
    action_pattern: str | None = None,
) -> List[str]:
    """Compute ready directories based on row status, eligibility, and dependencies.

    A directory is ready when it is not completed/submitted/waiting, all parents (if
    any) are completed, and (when row reports eligible dirs for the action) it appears
    in that eligible list.
    """

    project_path = Path(project.path)

    action_names = [a.name for a in spec.actions]
    completed: Set[str] = set()
    submitted: Set[str] = set()
    waiting: Set[str] = set()
    eligible_by_action: dict[str, Set[str]] = {}

    for name in action_names:
        completed |= _list_directories_with_status(project_path, "--completed", name)
        submitted |= _list_directories_with_status(project_path, "--submitted", name)
        waiting |= _list_directories_with_status(project_path, "--waiting", name)
        eligible_by_action[name] = _list_directories_with_status(
            project_path, "--eligible", name
        )

    blocked = completed | submitted | waiting

    ready: List[str] = []
    for action in spec.topological_actions():
        if not _matches_action(action.name, action_pattern):
            continue
        eligible_set = eligible_by_action.get(action.name, set())
        for job in project.find_jobs({"action": action.name}):
            if job.id in blocked:
                continue
            if job.id not in eligible_set:
                continue
            dep = action.dependency
            if dep:
                try:
                    parent_job = get_parent(job)
                except DependencyResolutionError:
                    continue
                if parent_job.id not in completed:
                    continue
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
