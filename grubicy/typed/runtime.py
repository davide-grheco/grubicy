"""Runtime helpers for loading and validating typed action parameters."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from .bindings import WorkflowBindings
from .errors import ActionParamsNotFoundError, TypedParamsValidationError
from grubicy.spec import ACTION_SP_KEY, DEFAULT_PARENT_SP_KEY

# Keys injected by grubicy's materialiser that are not user-defined params.
_RESERVED_SP_KEYS: frozenset[str] = frozenset({ACTION_SP_KEY, DEFAULT_PARENT_SP_KEY})


def _extract_action_raw_params(job: Any, action: str) -> dict[str, Any]:
    """Extract the raw parameter mapping for *action* from *job*.

    The function reads the signac state point and strips framework-reserved
    keys (``action``, ``parent_action``) so the remaining dict can be fed
    directly into a Pydantic ``model_validate`` call.

    Parameters
    ----------
    job
        A signac :class:`~signac.Job` instance.
    action
        The expected action name stored in ``job.sp["action"]``.

    Returns
    -------
    dict[str, Any]
        Plain mapping of user-defined parameter keys and their raw values.

    Raises
    ------
    ActionParamsNotFoundError
        If ``job.sp["action"]`` does not equal *action* (the job belongs to a
        different action) or if the state point has no ``action`` key at all.
    """
    sp = dict(job.sp)
    actual = sp.get("action")
    if actual != action:
        raise ActionParamsNotFoundError(
            f"Job {job.id!r} belongs to action {actual!r}, not {action!r}. "
            "Make sure you are passing the correct job."
        )
    return {k: v for k, v in sp.items() if k not in _RESERVED_SP_KEYS}


def load_action_params(
    job: Any,
    action_or_model: str | type[BaseModel] | WorkflowBindings,
    bindings: WorkflowBindings | None = None,
) -> Any:
    """Load and validate the parameters for an action from *job*.

    Three calling styles are supported:

    .. code-block:: python

        # 1. Original — explicit action name + bindings registry
        params = load_action_params(job, "train", bindings)

        # 2. Inferred action — pass the registry, action read from job.sp["action"]
        params = load_action_params(job, bindings)

        # 3. Direct model class — no registry needed, action read from job.sp["action"]
        params = load_action_params(job, TrainParams)

    Steps (all forms):

    1. Resolve the action name and Pydantic model class.
    2. Extract the raw parameter mapping from *job* via
       :func:`_extract_action_raw_params`.
    3. Validate the mapping with ``model_cls.model_validate(raw)``.
    4. Return the validated model instance.

    Parameters
    ----------
    job
        A signac :class:`~signac.Job` instance whose state point contains
        the parameters for the action.
    action_or_model
        One of:

        * ``str`` — explicit action name (original API); *bindings* must also
          be provided.
        * :class:`WorkflowBindings` — registry to look up the model; the
          action name is inferred from ``job.sp["action"]``.
        * ``type[BaseModel]`` subclass — used directly as the model class; the
          action name is inferred from ``job.sp["action"]``.
    bindings
        :class:`WorkflowBindings` registry.  Required only when
        *action_or_model* is a ``str``; ignored otherwise.

    Returns
    -------
    pydantic.BaseModel
        A validated instance of the resolved model class.

    Raises
    ------
    TypeError
        If *action_or_model* is a ``str`` but *bindings* is ``None``, or if an
        unsupported type is passed for *action_or_model*.
    UnknownActionBindingError
        If *action_or_model* is a ``str`` and *bindings* has no entry for it.
    ActionParamsNotFoundError
        If *job* does not belong to the resolved action, or if the action
        cannot be inferred (no ``action`` key in the state point).
    TypedParamsValidationError
        If Pydantic validation of the raw params fails.
    """
    if isinstance(action_or_model, str):
        # Original API: explicit action name + registry.
        if bindings is None:
            raise TypeError(
                "bindings must be provided when action_or_model is a string"
            )
        action = action_or_model
        model_cls = bindings.get(action)
    elif isinstance(action_or_model, WorkflowBindings):
        # Infer action from the state point, look up model in registry.
        action = job.sp.get("action")
        if not action:
            raise ActionParamsNotFoundError(
                f"Job {job.id!r} has no 'action' key in its state point. "
                "Cannot infer the action name automatically."
            )
        model_cls = action_or_model.get(action)
    elif isinstance(action_or_model, type) and issubclass(action_or_model, BaseModel):
        # Direct model class; infer action from the state point.
        action = job.sp.get("action")
        if not action:
            raise ActionParamsNotFoundError(
                f"Job {job.id!r} has no 'action' key in its state point. "
                "Cannot infer the action name automatically."
            )
        model_cls = action_or_model
    else:
        raise TypeError(
            f"Expected str, WorkflowBindings, or a BaseModel subclass; "
            f"got {type(action_or_model)!r}"
        )

    raw = _extract_action_raw_params(job, action)
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        raise TypedParamsValidationError(action, exc.errors()) from exc


def dump_action_params(model: BaseModel) -> dict[str, Any]:
    """Serialise a validated Pydantic model back to a plain :class:`dict`.

    Thin wrapper around :meth:`pydantic.BaseModel.model_dump`.

    Parameters
    ----------
    model
        A Pydantic model instance previously returned by
        :func:`load_action_params`.

    Returns
    -------
    dict[str, Any]
        Plain dictionary representation of the model.
    """
    return model.model_dump()
