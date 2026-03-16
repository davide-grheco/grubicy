"""Configuration schema and validation for signac-driven pipelines."""

from __future__ import annotations

import tomllib
from collections import deque
from dataclasses import dataclass
from itertools import product as iproduct
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


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
        """Create an :class:`ActionSpec` from a mapping.

        Parameters
        ----------
        data
            Mapping parsed from config (TOML/YAML). Must contain ``name`` and may
            provide ``sp_keys``, ``outputs``, ``runner``, and a ``deps`` table with
            ``action`` and optional ``sp_key``.

        Returns
        -------
        ActionSpec
            Parsed action definition with optional dependency.

        Raises
        ------
        ConfigValidationError
            If required fields are missing or have an unexpected structure.
        """
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
        """Create a workspace spec from a mapping.

        Parameters
        ----------
        data
            Mapping parsed from config; if empty defaults are used.

        Returns
        -------
        WorkspaceSpec
            Workspace settings (currently only ``value_file``).
        """
        if not data:
            return WorkspaceSpec()
        value_file = data.get("value_file", "signac_statepoint.json")
        return WorkspaceSpec(value_file=str(value_file))


def _expand_grid(
    grid: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Dict[str, Any]]]:
    """Expand a grid block into experiments via Cartesian product.

    Within each action, list-valued keys are swept and scalar keys are fixed.
    The per-action combinations are then crossed with each other.
    """
    action_names = list(grid.keys())
    action_combos: List[List[Dict[str, Any]]] = []

    for action_name in action_names:
        params = grid[action_name] or {}
        list_keys = [k for k, v in params.items() if isinstance(v, list)]
        scalar_params = {k: v for k, v in params.items() if not isinstance(v, list)}

        if list_keys:
            combos = [
                {**scalar_params, **dict(zip(list_keys, vals))}
                for vals in iproduct(*[params[k] for k in list_keys])
            ]
        else:
            combos = [scalar_params]

        action_combos.append(combos)

    return [
        {action_names[i]: combo for i, combo in enumerate(cross)}
        for cross in iproduct(*action_combos)
    ]


def _cross_grid_with_experiment(
    grid_space: List[Dict[str, Dict[str, Any]]],
    experiment: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Dict[str, Any]]]:
    """Cross a grid space with a single experiment.

    For each grid combo, the experiment's per-action params are merged in.
    Experiment params take precedence over grid params for the same action/key.
    """
    result = []
    for grid_exp in grid_space:
        merged: Dict[str, Dict[str, Any]] = {}
        for action, params in grid_exp.items():
            merged[action] = dict(params)
        for action, params in experiment.items():
            if action in merged:
                merged[action] = {**merged[action], **params}
            else:
                merged[action] = dict(params)
        result.append(merged)
    return result


def _parse_grid_blocks(
    raw_grids: List[Any],
) -> List[Tuple[Optional[str], List[Dict[str, Dict[str, Any]]]]]:
    """Parse and expand raw grid block entries.

    Returns a list of (name | None, expanded-combos) tuples.
    """
    result: List[Tuple[Optional[str], List[Dict[str, Dict[str, Any]]]]] = []
    for idx, grid in enumerate(raw_grids):
        if not isinstance(grid, dict):
            raise ConfigValidationError(f"Grid #{idx} must be a table/object")
        name = str(grid["name"]) if "name" in grid else None
        params = {k: v or {} for k, v in grid.items() if k != "name"}
        result.append((name, _expand_grid(params)))
    return result


def _parse_experiment_blocks(
    raw_experiments: List[Any],
) -> List[Tuple[Optional[List[str]], Dict[str, Dict[str, Any]]]]:
    """Parse raw experiment block entries.

    Returns a list of (grid_filter | None, params) tuples.

    grid_filter meanings:
      None  → apply all grids (default)
      []    → apply no grids (standalone experiment)
      [...] → apply only the named grids
    """
    result: List[Tuple[Optional[List[str]], Dict[str, Dict[str, Any]]]] = []
    for idx, exp in enumerate(raw_experiments):
        if not isinstance(exp, dict):
            raise ConfigValidationError(f"Experiment #{idx} must be a table/object")
        raw_filter = exp.get("grids")
        if raw_filter is not None and not isinstance(raw_filter, list):
            raise ConfigValidationError(
                f"Experiment #{idx}: 'grids' must be a list of grid names"
            )
        grid_filter: Optional[List[str]] = (
            None if raw_filter is None else [str(s) for s in raw_filter]
        )
        exp_params = {k: v or {} for k, v in exp.items() if k != "grids"}
        result.append((grid_filter, exp_params))
    return result


def _validate_grid_actions(
    grid_groups: List[Tuple[Optional[str], List[Dict[str, Dict[str, Any]]]]],
    action_names: Set[str],
) -> None:
    """Raise if any grid block references an action that was not defined."""
    for name, combos in grid_groups:
        label = f'Grid "{name}"' if name else "Unnamed grid"
        for combo in combos:
            for key in combo:
                if key not in action_names:
                    raise ConfigValidationError(
                        f"{label} references unknown action '{key}'"
                    )


def _validate_grid_references(
    parsed_experiments: List[Tuple[Optional[List[str]], Any]],
    all_grid_names: Set[str],
) -> None:
    """Raise if any experiment references a grid name that was not defined."""
    for idx, (grid_filter, _) in enumerate(parsed_experiments):
        if grid_filter:
            for ref in grid_filter:
                if ref not in all_grid_names:
                    raise ConfigValidationError(
                        f"Experiment #{idx} references unknown grid '{ref}'"
                    )


def _combine_grids_and_experiments(
    grid_groups: List[Tuple[Optional[str], List[Dict[str, Dict[str, Any]]]]],
    parsed_experiments: List[Tuple[Optional[List[str]], Dict[str, Dict[str, Any]]]],
) -> List[Dict[str, Dict[str, Any]]]:
    """Combine grid expansions with experiments into the final experiment list."""
    if not grid_groups:
        # No grids: each experiment is standalone
        return [params for _, params in parsed_experiments]
    if not parsed_experiments:
        # No experiments: grid expansions are the result
        return [exp for _, exps in grid_groups for exp in exps]
    # Both present: cross each experiment with its applicable grid space
    experiments: List[Dict[str, Dict[str, Any]]] = []
    for grid_filter, exp_params in parsed_experiments:
        if grid_filter is None:
            applicable = [exp for _, exps in grid_groups for exp in exps]
        elif not grid_filter:
            applicable = [{}]  # identity — standalone experiment
        else:
            applicable = [
                exp
                for name, exps in grid_groups
                if name in grid_filter
                for exp in exps
            ]
        experiments.extend(_cross_grid_with_experiment(applicable, exp_params))
    return experiments


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
        self._validate_experiments()

    @staticmethod
    def load(path: str | Path) -> "WorkflowSpec":
        """Load and validate a workflow spec from a TOML or YAML file."""
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
        """Construct a spec from a parsed mapping (already loaded TOML/YAML)."""
        raw_actions = data.get("actions") or data.get("action")
        if not raw_actions:
            raise ConfigValidationError("Configuration must include an 'actions' array")
        if not isinstance(raw_actions, Iterable):
            raise ConfigValidationError("'actions' must be a list of action tables")

        actions = [ActionSpec.from_mapping(e) for e in raw_actions]
        workspace = WorkspaceSpec.from_mapping(data.get("workspace", {}))

        raw_grids = data.get("grids") or data.get("grid") or []
        if raw_grids and not isinstance(raw_grids, list):
            raise ConfigValidationError("'grids' must be a list")
        grid_groups = _parse_grid_blocks(raw_grids)
        action_names = {a.name for a in actions}
        _validate_grid_actions(grid_groups, action_names)

        raw_experiments = data.get("experiments") or data.get("experiment") or []
        if raw_experiments and not isinstance(raw_experiments, list):
            raise ConfigValidationError("'experiments' must be a list")
        parsed_experiments = _parse_experiment_blocks(raw_experiments)

        _validate_grid_references(
            parsed_experiments, {n for n, _ in grid_groups if n is not None}
        )
        experiments = _combine_grids_and_experiments(grid_groups, parsed_experiments)

        return WorkflowSpec(actions=actions, experiments=experiments, workspace=workspace)

    def _validate_experiments(self) -> None:
        action_names = set(self._action_index)
        for idx, exp in enumerate(self._experiments):
            for key in exp:
                if key not in action_names:
                    raise ConfigValidationError(
                        f"Experiment #{idx} references unknown action '{key}'"
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
        """Return actions ordered so parents come before children.

        Raises
        ------
        ConfigValidationError
            If the dependency graph contains a cycle.
        """
        indegree = {a.name: 0 for a in self.actions}
        children: Dict[str, List[str]] = {a.name: [] for a in self.actions}

        for action in self.actions:
            if action.dependency:
                parent = action.dependency.action
                indegree[action.name] += 1
                children[parent].append(action.name)

        queue = deque(name for name, deg in indegree.items() if deg == 0)

        ordered: List[str] = []

        while queue:
            current = queue.popleft()
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
        """List of experiment parameter blocks copied from the config."""

        return list(self._experiments)

    def get_action(self, name: str) -> ActionSpec:
        """Return an action by name or raise :class:`ConfigValidationError`."""
        try:
            return self._action_index[name]
        except KeyError as exc:
            raise ConfigValidationError(f"Unknown action '{name}'") from exc


def load_spec(path: str | Path) -> WorkflowSpec:
    """Load and validate a workflow spec from disk (TOML or YAML)."""

    return WorkflowSpec.load(path)
