"""Registry mapping action names to Pydantic model classes."""

from __future__ import annotations

from pydantic import BaseModel

from .errors import UnknownActionBindingError


class WorkflowBindings:
    """Registry that maps action names to Pydantic :class:`~pydantic.BaseModel` classes.

    Usage::

        bindings = (
            WorkflowBindings()
            .bind("train", TrainParams)
            .bind("evaluate", EvalParams)
        )

    """

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseModel]] = {}

    def bind(self, action_name: str, model_cls: type[BaseModel]) -> "WorkflowBindings":
        """Register *model_cls* as the schema for *action_name*.

        Parameters
        ----------
        action_name
            Workflow action identifier (must match the ``action`` key in the
            signac state point).
        model_cls
            A Pydantic :class:`~pydantic.BaseModel` subclass.

        Returns
        -------
        WorkflowBindings
            The same registry instance, for method chaining.

        Raises
        ------
        ValueError
            If *action_name* already has a registered binding.
        TypeError
            If *model_cls* is not a Pydantic BaseModel subclass.
        """
        if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
            raise TypeError(
                f"model_cls must be a Pydantic BaseModel subclass, got {model_cls!r}"
            )
        if action_name in self._registry:
            raise ValueError(
                f"Action '{action_name}' is already bound to {self._registry[action_name]!r}. "
                "Each action may only have one binding."
            )
        self._registry[action_name] = model_cls
        return self

    def get(self, action_name: str) -> type[BaseModel]:
        """Return the model class registered for *action_name*.

        Raises
        ------
        UnknownActionBindingError
            If no binding exists for *action_name*.
        """
        try:
            return self._registry[action_name]
        except KeyError as exc:
            raise UnknownActionBindingError(
                f"No binding registered for action '{action_name}'. "
                f"Registered actions: {sorted(self._registry)}"
            ) from exc

    def has(self, action_name: str) -> bool:
        """Return ``True`` if *action_name* has a registered binding."""
        return action_name in self._registry
