"""Typed action parameter binding with Pydantic.

Maps grubicy action state point values to validated Pydantic v2 models,
replacing raw ``job.sp["key"]`` access with typed, constraint-checked objects.

Three calling styles are supported::

    from pydantic import BaseModel, Field
    from grubicy.typed import WorkflowBindings, load_action_params

    class TrainParams(BaseModel):
        lr: float = 0.01
        epochs: int
        batch_size: int = 32

    # 1) Explicit action name + registry
    bindings = WorkflowBindings().bind("train", TrainParams)
    params = load_action_params(job, "train", bindings)

    # 2) Action inferred from job.sp["action"], looked up in registry
    params = load_action_params(job, bindings)

    # 3) Direct model class — no registry needed, action inferred
    params = load_action_params(job, TrainParams)

    # params.lr, params.epochs, params.batch_size are fully typed

Public API
----------
- :class:`WorkflowBindings` — registry of action → model class mappings.
- :func:`load_action_params` — extract and validate params from a job.
- :func:`dump_action_params` — serialise a validated model to a plain dict.

Exceptions
----------
- :exc:`~grubicy.typed.errors.UnknownActionBindingError`
- :exc:`~grubicy.typed.errors.ActionParamsNotFoundError`
- :exc:`~grubicy.typed.errors.TypedParamsValidationError`
"""

from .bindings import WorkflowBindings
from .errors import (
    ActionParamsNotFoundError,
    TypedParamsValidationError,
    UnknownActionBindingError,
)
from .runtime import dump_action_params, load_action_params

__all__ = [
    "WorkflowBindings",
    "load_action_params",
    "dump_action_params",
    "UnknownActionBindingError",
    "ActionParamsNotFoundError",
    "TypedParamsValidationError",
]
