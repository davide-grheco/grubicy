"""Schema migrations with cascading dependency rewrites."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import signac

from .spec import ConfigValidationError, WorkflowSpec

StatePoint = Dict[str, Any]


class MigrationCollisionError(Exception):
    """Raised when multiple jobs converge to the same new state point."""


class MigrationLockError(Exception):
    """Raised when a migration lock cannot be acquired."""


@dataclass
class MigrationEntry:
    old_id: str
    new_id: str
    old_sp: StatePoint
    new_sp: StatePoint


@dataclass
class MigrationPlan:
    action_name: str
    entries: List[MigrationEntry]
    collisions: List[str] = field(default_factory=list)
    plan_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "entries": [
                {
                    "old_id": e.old_id,
                    "new_id": e.new_id,
                    "old_sp": e.old_sp,
                    "new_sp": e.new_sp,
                }
                for e in self.entries
            ],
            "collisions": self.collisions,
        }

    @staticmethod
    def from_path(path: str | Path) -> "MigrationPlan":
        data = json.loads(Path(path).read_text())
        entries = [
            MigrationEntry(
                old_id=e["old_id"],
                new_id=e["new_id"],
                old_sp=e["old_sp"],
                new_sp=e["new_sp"],
            )
            for e in data["entries"]
        ]
        return MigrationPlan(
            action_name=data["action_name"],
            entries=entries,
            collisions=data.get("collisions", []),
            plan_path=Path(path),
        )


@dataclass
class MigrationReport:
    action_name: str
    updated_actions: Dict[str, int]
    collisions: List[str]
    plan_path: Optional[Path]


def _maybe_move_workspace(old_path: Path, new_path: Path) -> None:
    if old_path == new_path:
        return
    if not old_path.exists():
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(old_path, new_path, dirs_exist_ok=True)


def _default_plan_path(project: signac.Project, action_name: str) -> Path:
    root = Path(project.path)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    target = root / ".pipeline_migrations" / f"plan_{action_name}_{stamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def plan_migration(
    spec: WorkflowSpec,
    project: signac.Project,
    action_name: str,
    sp_transform: Callable[[StatePoint], StatePoint],
    selection: Optional[Mapping[str, Any]] = None,
    collision_strategy: str = "abort",
    plan_path: Optional[Path] = None,
) -> MigrationPlan:
    """Create a migration plan for a single action.

    The plan computes old->new state points and detects collisions before any mutation.
    """

    if collision_strategy not in {"abort", "keep-first"}:
        raise ValueError("collision_strategy must be 'abort' or 'keep-first'")

    if action_name not in {a.name for a in spec.actions}:
        raise ConfigValidationError(f"Unknown action '{action_name}'")

    query = {"action": action_name}
    if selection:
        query.update(selection)

    entries: List[MigrationEntry] = []
    collision_targets: Dict[str, List[str]] = {}

    for job in project.find_jobs(query):
        old_sp = dict(job.sp)
        new_sp = dict(sp_transform(dict(job.sp)))
        # Ensure action remains consistent.
        new_sp["action"] = action_name
        new_job = project.open_job(new_sp)
        entry = MigrationEntry(
            old_id=job.id, new_id=new_job.id, old_sp=old_sp, new_sp=new_sp
        )
        entries.append(entry)
        collision_targets.setdefault(new_job.id, []).append(job.id)

    collisions = [
        target for target, sources in collision_targets.items() if len(sources) > 1
    ]
    if collisions and collision_strategy == "abort":
        raise MigrationCollisionError(
            f"Collisions detected for new job ids: {collisions}"
        )

    if collision_strategy == "keep-first":
        filtered: List[MigrationEntry] = []
        seen = set()
        for entry in entries:
            if entry.new_id in seen:
                continue
            seen.add(entry.new_id)
            filtered.append(entry)
        entries = filtered

    plan = MigrationPlan(
        action_name=action_name,
        entries=entries,
        collisions=collisions,
        plan_path=plan_path,
    )

    target_path = plan_path or _default_plan_path(project, action_name)
    target_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    plan.plan_path = target_path
    return plan


def _acquire_lock(project: signac.Project) -> Path:
    lock_path = Path(project.path) / ".pipeline_lock"
    try:
        lock_path.touch(exist_ok=False)
    except FileExistsError as exc:
        raise MigrationLockError(
            "Another migration appears to be running; lock exists"
        ) from exc
    return lock_path


def _release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def execute_migration(
    spec: WorkflowSpec, project: signac.Project, plan: MigrationPlan
) -> MigrationReport:
    """Execute a migration plan and cascade dependency pointer rewrites."""

    lock = _acquire_lock(project)
    updated_counts: Dict[str, int] = {}
    try:
        # Apply primary action migration
        mapping_by_action: Dict[str, Dict[str, str]] = {}
        primary_map: Dict[str, str] = {}
        for entry in plan.entries:
            job = project.open_job(id=entry.old_id)
            old_path = Path(job.path)
            if job.sp == entry.new_sp:
                primary_map[entry.old_id] = entry.new_id
                continue
            job.sp = entry.new_sp
            new_path = Path(project.open_job(entry.new_sp).path)
            _maybe_move_workspace(old_path, new_path)
            primary_map[entry.old_id] = entry.new_id
            updated_counts[plan.action_name] = (
                updated_counts.get(plan.action_name, 0) + 1
            )
        mapping_by_action[plan.action_name] = primary_map

        # Cascade to downstream actions
        topo = spec.topological_actions()
        downstream_started = False
        for action in topo:
            if action.name == plan.action_name:
                downstream_started = True
                continue
            if not downstream_started:
                continue
            if not action.dependency:
                continue
            parent_action = action.dependency.action
            if parent_action not in mapping_by_action:
                continue
            parent_map = mapping_by_action[parent_action]

            current_map: Dict[str, str] = {}
            for job in project.find_jobs({"action": action.name}):
                dep_key = action.dependency.sp_key
                parent_id = job.sp.get(dep_key)
                if parent_id not in parent_map:
                    continue
                new_parent_id = parent_map[parent_id]
                old_id = job.id
                old_path = Path(job.path)
                new_sp = dict(job.sp)
                new_sp[dep_key] = new_parent_id
                new_sp["action"] = action.name
                new_job = project.open_job(new_sp)
                if new_job.id == job.id:
                    continue
                job.sp = new_sp
                new_path = Path(new_job.path)
                _maybe_move_workspace(old_path, new_path)
                # Update deps_meta for the parent
                parent_job = project.open_job(id=new_parent_id)
                deps_meta = dict(job.doc.get("deps_meta", {}))
                deps_meta[parent_job.sp.get("action", parent_job.id)] = {
                    "job_id": parent_job.id,
                    "statepoint": dict(parent_job.sp),
                }
                job.doc["deps_meta"] = deps_meta
                current_map[old_id] = new_job.id
                updated_counts[action.name] = updated_counts.get(action.name, 0) + 1
            if current_map:
                mapping_by_action[action.name] = current_map

        return MigrationReport(
            action_name=plan.action_name,
            updated_actions=updated_counts,
            collisions=plan.collisions,
            plan_path=plan.plan_path,
        )
    finally:
        _release_lock(lock)
