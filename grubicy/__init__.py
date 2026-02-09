"""Lightweight config-driven helpers for signac pipelines.

This package provides a minimal schema for describing actions, experiments,
and dependencies, plus helpers to materialize jobs, resolve parent pointers,
and emit row workflows.
"""

from .spec import ActionSpec, DependencySpec, WorkspaceSpec, WorkflowSpec, load_spec
from .context import WorkflowContext
from .materialize import MaterializationReport, materialize
from .helpers import (
    get_parent,
    open_parent_folder,
    parent_file,
    parent_product_exists,
    parent_path,
    iter_parent_products,
    open_job_from_directory,
    get_parent_doc,
)
from .row_render import render_row_workflow
from .migrate import (
    MigrationPlan,
    MigrationReport,
    execute_migration,
    plan_migration,
)
from .collect import CollectedRow, collect_params_with_parents

__all__ = [
    "ActionSpec",
    "DependencySpec",
    "WorkspaceSpec",
    "WorkflowSpec",
    "WorkflowContext",
    "MaterializationReport",
    "materialize",
    "get_parent",
    "open_parent_folder",
    "parent_file",
    "parent_product_exists",
    "parent_path",
    "iter_parent_products",
    "open_job_from_directory",
    "get_parent_doc",
    "render_row_workflow",
    "MigrationPlan",
    "MigrationReport",
    "plan_migration",
    "execute_migration",
    "CollectedRow",
    "collect_params_with_parents",
    "load_spec",
]
