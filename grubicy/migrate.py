"""Schema migrations with cascading dependency rewrites."""

from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from filelock import FileLock, Timeout
import msgspec
import signac

from .spec import ConfigValidationError, WorkflowSpec

StatePoint = Dict[str, Any]


class MigrationCollisionError(Exception):
    """Raised when multiple jobs converge to the same new state point."""


class MigrationLockError(Exception):
    """Raised when a migration lock cannot be acquired."""


class MigrationEntry(msgspec.Struct):
    old_id: str
    new_id: str
    old_sp: StatePoint
    new_sp: StatePoint


class MigrationPlan(msgspec.Struct):
    action_name: str
    entries: List[MigrationEntry]
    collisions: List[str] = msgspec.field(default_factory=list)

    @classmethod
    def from_path(cls, path: Path) -> "MigrationPlan":
        return msgspec.json.decode(path.read_bytes(), type=cls)

    def save(self, path: Path) -> None:
        path.write_bytes(msgspec.json.encode(self))

    def to_json(self) -> str:
        """Return the plan as a JSON string."""

        return msgspec.json.encode(self).decode("utf-8")


class MigrationReport(msgspec.Struct):
    action_name: str
    updated_actions: Dict[str, int]
    collisions: List[str]
    plan_path: Optional[str]

    def to_json(self) -> str:
        """Return the report as a JSON string."""

        return msgspec.json.encode(self).decode("utf-8")


class MigrationProgress(msgspec.Struct):
    action: str
    mapping: Dict[str, Dict[str, str]]
    updated_counts: Dict[str, int]
    collisions: List[str]
    done: bool
    timestamp: str


def _run_dir(
    project: signac.Project, plan: MigrationPlan, plan_path: Optional[Path]
) -> Path:
    base = Path(project.path) / ".pipeline_migrations"
    stem = (
        plan_path.stem
        if plan_path
        else f"plan_{plan.action_name}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    )
    # try to reuse timestamp suffix if present
    parts = stem.split("_")
    stamp = (
        parts[-1] if len(parts) >= 3 else datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    )
    run_dir = base / f"run_{plan.action_name}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_progress(run_dir: Path, progress: "MigrationProgress") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "progress.json"
    path.write_bytes(msgspec.json.encode(progress))


def _read_progress(path: Path) -> Optional["MigrationProgress"]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        return msgspec.json.decode(raw, type=MigrationProgress)
    except msgspec.DecodeError:
        return None


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
) -> tuple[MigrationPlan, Path]:
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
        seen = set()
        unique = []
        for e in entries:
            if e.new_id not in seen:
                seen.add(e.new_id)
                unique.append(e)
        entries = unique

    plan = MigrationPlan(
        action_name=action_name, entries=entries, collisions=collisions
    )
    target_path = plan_path or _default_plan_path(project, action_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    plan.save(target_path)
    return plan, target_path


def _acquire_lock(project: signac.Project) -> FileLock:
    lock_path = Path(project.path) / ".pipeline_lock"
    lock = FileLock(lock_path)
    try:
        lock.acquire(timeout=0)
    except Timeout as exc:
        raise MigrationLockError(
            "Another migration appears to be running; lock exists"
        ) from exc
    return lock


class MigrationExecutor:
    """Execute a migration plan and cascade dependency pointer rewrites."""

    def __init__(
        self,
        spec: WorkflowSpec,
        project: signac.Project,
        plan: MigrationPlan,
        run_dir: Path,
        resume: bool,
        plan_path: Optional[Path],
    ) -> None:
        self.spec = spec
        self.project = project
        self.plan = plan
        self.run_dir = run_dir
        self.plan_path = plan_path
        self.progress_path = run_dir / "progress.json"
        self.mapping_by_action: Dict[str, Dict[str, str]] = {}
        self.updated_counts = defaultdict(int)
        if resume:
            self._load_progress()

    def run(self) -> MigrationReport:
        primary_map = self.mapping_by_action.get(self.plan.action_name, {})
        if not primary_map:
            primary_map = self._apply_primary_action()
            self.mapping_by_action[self.plan.action_name] = primary_map
            self._write_progress(done=False)

        self._cascade_downstream()
        self._write_progress(done=True)

        return MigrationReport(
            action_name=self.plan.action_name,
            updated_actions=self.updated_counts,
            collisions=self.plan.collisions,
            plan_path=str(self.plan_path) if self.plan_path else None,
        )

    def _apply_primary_action(self) -> Dict[str, str]:
        primary_map: Dict[str, str] = {}
        for entry in self.plan.entries:
            job = self.project.open_job(id=entry.old_id)
            old_path = Path(job.path)
            if job.sp == entry.new_sp:
                primary_map[entry.old_id] = entry.new_id
                continue
            job.sp = entry.new_sp
            new_path = Path(self.project.open_job(entry.new_sp).path)
            _maybe_move_workspace(old_path, new_path)
            primary_map[entry.old_id] = entry.new_id
            self._increment_updated(self.plan.action_name)
        return primary_map

    def _cascade_downstream(self) -> None:
        topo = self.spec.topological_actions()
        downstream_started = False
        for action in topo:
            if action.name == self.plan.action_name:
                downstream_started = True
                continue
            if not downstream_started or not action.dependency:
                continue

            parent_action = action.dependency.action
            if parent_action not in self.mapping_by_action:
                continue

            parent_map = self.mapping_by_action[parent_action]
            current_map: Dict[str, str] = self.mapping_by_action.get(action.name, {})

            for job in self.project.find_jobs({"action": action.name}):
                dep_key = action.dependency.sp_key
                parent_id = job.sp.get(dep_key)
                if parent_id not in parent_map:
                    continue

                new_parent_id = parent_map[parent_id]
                old_id = job.id
                new_sp = dict(job.sp)
                new_sp[dep_key] = new_parent_id
                new_sp["action"] = action.name
                new_job = self.project.open_job(new_sp)
                if new_job.id == job.id:
                    continue

                old_path = Path(job.path)
                job.sp = new_sp
                new_path = Path(new_job.path)
                _maybe_move_workspace(old_path, new_path)
                self._update_deps_meta(job, new_parent_id)

                current_map[old_id] = new_job.id
                self._increment_updated(action.name)

            if current_map:
                self.mapping_by_action[action.name] = current_map
                self._write_progress(done=False)

    def _update_deps_meta(self, job: signac.Job, new_parent_id: str) -> None:
        parent_job = self.project.open_job(id=new_parent_id)
        deps_meta = dict(job.doc.get("deps_meta", {}))
        deps_meta[parent_job.sp.get("action", parent_job.id)] = {
            "job_id": parent_job.id,
            "statepoint": dict(parent_job.sp),
        }
        job.doc["deps_meta"] = deps_meta

    def _increment_updated(self, action_name: str) -> None:
        self.updated_counts[action_name] += 1

    def _write_progress(self, *, done: bool) -> None:
        progress = MigrationProgress(
            action=self.plan.action_name,
            mapping=self.mapping_by_action,
            updated_counts=dict(self.updated_counts),
            collisions=self.plan.collisions,
            done=done,
            timestamp=datetime.now(UTC).isoformat(),
        )
        _write_progress(self.run_dir, progress)

    def _load_progress(self) -> None:
        progress = _read_progress(self.progress_path)
        if progress is None:
            return
        self.mapping_by_action = progress.mapping
        self.updated_counts = progress.updated_counts


def execute_migration(
    spec: WorkflowSpec,
    project: signac.Project,
    plan: MigrationPlan,
    plan_path: Optional[Path] = None,
    resume: bool = True,
) -> MigrationReport:
    """Execute a migration plan and cascade dependency pointer rewrites.

    Writes progress under ``.pipeline_migrations`` so a rerun can resume safely.
    """

    lock = _acquire_lock(project)
    try:
        executor = MigrationExecutor(
            spec=spec,
            project=project,
            plan=plan,
            run_dir=_run_dir(project, plan, plan_path),
            resume=resume,
            plan_path=plan_path,
        )
        return executor.run()
    finally:
        lock.release()
