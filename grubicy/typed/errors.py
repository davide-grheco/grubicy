"""Exceptions raised by the grubicy.typed runtime helpers."""

from __future__ import annotations


class UnknownActionBindingError(Exception):
    """Raised when no Pydantic model is registered for the requested action."""


class ActionParamsNotFoundError(Exception):
    """Raised when a job does not contain parameters for the requested action."""


class TypedParamsValidationError(Exception):
    """Raised when Pydantic validation fails for action parameters.

    The exception message lists every validation error prefixed with
    ``<action>.<field_path>`` so failures are easy to locate.

    Attributes
    ----------
    action
        Name of the action whose params failed validation.
    validation_errors
        Raw list of Pydantic error dicts (from ``ValidationError.errors()``).
    """

    def __init__(self, action: str, validation_errors: list) -> None:
        self.action = action
        self.validation_errors = validation_errors

        lines: list[str] = []
        for error in validation_errors:
            loc_parts = ".".join(str(part) for part in error["loc"])
            path = f"{action}.{loc_parts}" if loc_parts else action
            lines.append(f"{path}: {error['msg']}")

        super().__init__("\n".join(lines))
