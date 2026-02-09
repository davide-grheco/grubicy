"""Lightweight config-driven helpers for signac pipelines.

This package provides a minimal schema for describing actions, experiments,
and dependencies, plus helpers to materialize jobs, resolve parent pointers,
and emit row workflows.
"""

from .spec import ActionSpec, DependencySpec, WorkspaceSpec, WorkflowSpec, load_spec
from .context import WorkflowContext
from .materialize import MaterializationReport
from .helpers import get_parent, open_parent_folder, parent_file, iter_parent_products
from .row_render import render_row_workflow

__all__ = [
    "ActionSpec",
    "DependencySpec",
    "WorkspaceSpec",
    "WorkflowSpec",
    "WorkflowContext",
    "MaterializationReport",
    "get_parent",
    "open_parent_folder",
    "parent_file",
    "iter_parent_products",
    "render_row_workflow",
    "load_spec",
]
