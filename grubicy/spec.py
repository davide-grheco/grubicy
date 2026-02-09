"""Configuration schema and validation for signac-driven pipelines."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class ConfigValidationError(Exception):
    """Raised when a configuration file fails validation."""


@dataclass(frozen=True)
class DependencySpec:
    """Represents a single parent dependency for an action.

    Attributes
    ----------
    action
        Name of the parent action.
    sp_key
        State point key used to store the parent job id in the child job.
    """

    action: str
    sp_key: str = "parent_action"


@dataclass(frozen=True)
class ActionSpec:
    """Describes an action (stage) in the workflow."""

    name: str
    sp_keys: List[str]
    dependency: Optional[DependencySpec] = None
    outputs: List[str] | None = None
    runner: Optional[str] = None

    @staticmethod
    def from_mapping(data: Dict[str, Any]) -> "ActionSpec":
        if "name" not in data:
            raise ConfigValidationError("Each action must define a name")

        name = str(data["name"])
        sp_keys = list(map(str, data.get("sp_keys", [])))
        outputs = data.get("outputs")
        runner = data.get("runner")

        raw_dep = data.get("deps") or data.get("dependency")
        dependency = None
        if raw_dep:
            if not isinstance(raw_dep, dict):
                raise ConfigValidationError(
                    "deps must be a table/object with 'action' and optional 'sp_key'"
                )
            dep_action = raw_dep.get("action")
            if not dep_action:
                raise ConfigValidationError(
                    "deps.action is required when specifying a dependency"
                )
            sp_key = raw_dep.get("sp_key", "parent_action")
            dependency = DependencySpec(action=str(dep_action), sp_key=str(sp_key))

        return ActionSpec(
            name=name,
            sp_keys=sp_keys,
            dependency=dependency,
            outputs=outputs,
            runner=runner,
        )


@dataclass(frozen=True)
class WorkspaceSpec:
    """Metadata about the workspace configuration."""

    value_file: str = "signac_statepoint.json"

    @staticmethod
    def from_mapping(data: Dict[str, Any]) -> "WorkspaceSpec":
        if not data:
            return WorkspaceSpec()
        value_file = data.get("value_file", "signac_statepoint.json")
        return WorkspaceSpec(value_file=str(value_file))


class WorkflowSpec:
    """Parsed configuration for a workflow.

    Provides validation, topological ordering, and access to experiments.
    """

    def __init__(
        self,
        actions: List[ActionSpec],
        experiments: List[Dict[str, Dict[str, Any]]],
        workspace: WorkspaceSpec,
    ):
        self.actions = actions
        self._experiments = experiments
        self.workspace = workspace
        self._action_index = {a.name: a for a in actions}
        if len(self._action_index) != len(actions):
            raise ConfigValidationError("Action names must be unique")
        self._validate_dependencies()

    @staticmethod
    def load(path: str | Path) -> "WorkflowSpec":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        data: Dict[str, Any]
        if path.suffix.lower() in {".toml"}:
            data = tomllib.loads(path.read_text())
        elif path.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise ImportError("PyYAML is required to load YAML configs") from exc
            data = yaml.safe_load(path.read_text()) or {}
        else:
            raise ConfigValidationError(f"Unsupported config extension: {path.suffix}")

        return WorkflowSpec.from_mapping(data)

    @staticmethod
    def from_mapping(data: Dict[str, Any]) -> "WorkflowSpec":
        raw_actions = data.get("actions") or data.get("action")
        if not raw_actions:
            raise ConfigValidationError("Configuration must include an 'actions' array")
        if not isinstance(raw_actions, Iterable):
            raise ConfigValidationError("'actions' must be a list of action tables")

        actions = [ActionSpec.from_mapping(entry) for entry in raw_actions]

        workspace = WorkspaceSpec.from_mapping(data.get("workspace", {}))

        raw_experiments = data.get("experiments") or data.get("experiment") or []
        if raw_experiments and not isinstance(raw_experiments, Iterable):
            raise ConfigValidationError("'experiments' must be a list")

        experiments: List[Dict[str, Dict[str, Any]]] = []
        for idx, exp in enumerate(raw_experiments):
            if not isinstance(exp, dict):
                raise ConfigValidationError(f"Experiment #{idx} must be a table/object")
            # Each key is an action name mapping to params.
            experiments.append({k: v or {} for k, v in exp.items()})

        return WorkflowSpec(
            actions=actions, experiments=experiments, workspace=workspace
        )

    def _validate_dependencies(self) -> None:
        action_names = {a.name for a in self.actions}
        for action in self.actions:
            if action.dependency and action.dependency.action not in action_names:
                raise ConfigValidationError(
                    f"Action '{action.name}' depends on undefined action '{action.dependency.action}'"
                )
        # Check cycles via topological sort attempt
        self.topological_actions()

    def topological_actions(self) -> List[ActionSpec]:
        indegree = {a.name: 0 for a in self.actions}
        children: Dict[str, List[str]] = {a.name: [] for a in self.actions}
        for action in self.actions:
            if action.dependency:
                parent = action.dependency.action
                indegree[action.name] += 1
                children[parent].append(action.name)

        queue = [name for name, deg in indegree.items() if deg == 0]
        ordered: List[str] = []
        while queue:
            current = queue.pop(0)
            ordered.append(current)
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered) != len(indegree):
            raise ConfigValidationError("Action graph contains a cycle")

        return [self._action_index[name] for name in ordered]

    @property
    def experiments(self) -> List[Dict[str, Dict[str, Any]]]:
        return list(self._experiments)

    def get_action(self, name: str) -> ActionSpec:
        try:
            return self._action_index[name]
        except KeyError as exc:
            raise ConfigValidationError(f"Unknown action '{name}'") from exc


def load_spec(path: str | Path) -> WorkflowSpec:
    """Load and validate a workflow spec from disk."""

    return WorkflowSpec.load(path)
