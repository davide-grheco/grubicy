"""Convenience helpers for accessing parent jobs and their files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import signac


class DependencyResolutionError(Exception):
    """Raised when a job's parent cannot be resolved."""


def get_parent(job: signac.Job) -> signac.Job:
    """Return the parent job referenced by ``parent_action`` in the state point."""

    key = "parent_action"
    if key not in job.sp:
        raise DependencyResolutionError(f"Job {job.id} has no '{key}' state point key")
    parent_id = job.sp[key]
    project = job.project
    try:
        return project.open_job(id=str(parent_id))
    except LookupError as exc:
        raise DependencyResolutionError(
            f"Parent job '{parent_id}' not found for job {job.id}"
        ) from exc


def open_parent_folder(job: signac.Job, path: str | Path | None = None) -> Path:
    """Return the filesystem path to the parent job workspace, optionally joined with ``path``."""

    parent = get_parent(job)
    base = Path(parent.path)
    return base / Path(path) if path is not None else base


def parent_file(job: signac.Job, relpath: str | Path, must_exist: bool = True) -> Path:
    """Return an absolute path to a file in the parent workspace."""

    path = open_parent_folder(job, relpath)
    if must_exist and not path.exists():
        raise FileNotFoundError(path)
    return path


def iter_parent_products(job: signac.Job, pattern: str = "*") -> Iterator[Path]:
    """Yield paths matching a glob pattern inside the parent workspace."""

    parent = get_parent(job)
    return Path(parent.path).glob(pattern)
