"""Tests for grubicy.typed — WorkflowBindings and load_action_params."""

from __future__ import annotations

import pytest
import signac
from pydantic import BaseModel, Field

from grubicy.typed import (
    WorkflowBindings,
    dump_action_params,
    load_action_params,
)
from grubicy.typed.errors import (
    ActionParamsNotFoundError,
    TypedParamsValidationError,
    UnknownActionBindingError,
)


# ---------------------------------------------------------------------------
# Helpers / shared models
# ---------------------------------------------------------------------------


class TrainParams(BaseModel):
    lr: float = 0.01
    epochs: int
    batch_size: int = 32


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return signac.init_project("test-typed")


def _job(project, sp: dict):
    job = project.open_job(sp)
    job.init()
    return job


# ---------------------------------------------------------------------------
# WorkflowBindings
# ---------------------------------------------------------------------------


def test_bindings_has_false_before_registration():
    bindings = WorkflowBindings()
    assert not bindings.has("train")


def test_bindings_has_true_after_registration():
    bindings = WorkflowBindings().bind("train", TrainParams)
    assert bindings.has("train")


def test_bindings_get_returns_registered_class():
    bindings = WorkflowBindings().bind("train", TrainParams)
    assert bindings.get("train") is TrainParams


def test_bindings_get_raises_for_unknown_action():
    bindings = WorkflowBindings()
    with pytest.raises(UnknownActionBindingError, match="train"):
        bindings.get("train")


def test_bindings_duplicate_raises():
    bindings = WorkflowBindings().bind("train", TrainParams)
    with pytest.raises(ValueError, match="already bound"):
        bindings.bind("train", TrainParams)


def test_bindings_rejects_non_model():
    bindings = WorkflowBindings()
    with pytest.raises(TypeError):
        bindings.bind("train", dict)  # type: ignore[arg-type]


def test_bindings_chaining():
    class EvalParams(BaseModel):
        threshold: float

    bindings = WorkflowBindings().bind("train", TrainParams).bind("eval", EvalParams)
    assert bindings.has("train")
    assert bindings.has("eval")


# ---------------------------------------------------------------------------
# 1. Successful validation
# ---------------------------------------------------------------------------


def test_load_action_params_success(project):
    job = _job(project, {"action": "train", "lr": 0.001, "epochs": 10})
    bindings = WorkflowBindings().bind("train", TrainParams)

    result = load_action_params(job, "train", bindings)

    assert isinstance(result, TrainParams)
    assert result.lr == pytest.approx(0.001)
    assert result.epochs == 10
    assert result.batch_size == 32  # default applied


def test_load_action_params_inferred_from_bindings(project):
    job = _job(project, {"action": "train", "lr": 0.002, "epochs": 8})
    bindings = WorkflowBindings().bind("train", TrainParams)

    result = load_action_params(job, bindings)

    assert isinstance(result, TrainParams)
    assert result.lr == pytest.approx(0.002)
    assert result.epochs == 8


def test_load_action_params_direct_model_class(project):
    job = _job(project, {"action": "train", "lr": 0.003, "epochs": 4})

    result = load_action_params(job, TrainParams)

    assert isinstance(result, TrainParams)
    assert result.lr == pytest.approx(0.003)
    assert result.epochs == 4


# ---------------------------------------------------------------------------
# 2. Type coercion and defaults
# ---------------------------------------------------------------------------


def test_load_action_params_coercion(project):
    """String values are coerced to the declared type."""
    job = _job(project, {"action": "train", "lr": "0.005", "epochs": "7"})
    bindings = WorkflowBindings().bind("train", TrainParams)

    result = load_action_params(job, "train", bindings)

    assert result.lr == pytest.approx(0.005)
    assert result.epochs == 7


def test_load_action_params_defaults(project):
    """Fields with defaults are filled in when absent from the state point."""
    job = _job(project, {"action": "train", "epochs": 3})
    bindings = WorkflowBindings().bind("train", TrainParams)

    result = load_action_params(job, "train", bindings)

    assert result.lr == pytest.approx(0.01)
    assert result.batch_size == 32


# ---------------------------------------------------------------------------
# 3. Missing required field → TypedParamsValidationError
# ---------------------------------------------------------------------------


def test_load_action_params_missing_required_field(project):
    job = _job(project, {"action": "train", "lr": 0.001})  # epochs is required
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(TypedParamsValidationError) as exc_info:
        load_action_params(job, "train", bindings)

    msg = str(exc_info.value)
    assert "train.epochs" in msg


# ---------------------------------------------------------------------------
# 4. Invalid value / constraint → TypedParamsValidationError
# ---------------------------------------------------------------------------


def test_load_action_params_constraint_violation(project):
    class BoundedParams(BaseModel):
        p1: int = Field(ge=0)

    job = _job(project, {"action": "s1", "p1": -5})
    bindings = WorkflowBindings().bind("s1", BoundedParams)

    with pytest.raises(TypedParamsValidationError) as exc_info:
        load_action_params(job, "s1", bindings)

    msg = str(exc_info.value)
    assert "s1.p1" in msg


def test_load_action_params_wrong_type(project):
    class StrictParams(BaseModel):
        count: int

    job = _job(project, {"action": "s1", "count": "not-an-int"})
    bindings = WorkflowBindings().bind("s1", StrictParams)

    with pytest.raises(TypedParamsValidationError) as exc_info:
        load_action_params(job, "s1", bindings)

    assert "s1.count" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. Unknown action binding → UnknownActionBindingError
# ---------------------------------------------------------------------------


def test_load_action_params_unknown_binding(project):
    job = _job(project, {"action": "train", "epochs": 5})
    bindings = WorkflowBindings()  # empty — no bindings registered

    with pytest.raises(UnknownActionBindingError):
        load_action_params(job, "train", bindings)


# ---------------------------------------------------------------------------
# 6. Job for a different action → ActionParamsNotFoundError
# ---------------------------------------------------------------------------


def test_load_action_params_wrong_action_job(project):
    job = _job(project, {"action": "infer", "batch": 16})
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, "train", bindings)


def test_load_action_params_no_action_key(project):
    """Jobs without an 'action' key in the state point raise ActionParamsNotFoundError."""
    job = _job(project, {"epochs": 5})  # no "action" key
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, "train", bindings)


def test_load_action_params_no_action_key_inferred(project):
    job = _job(project, {"epochs": 5})  # no "action" key
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, bindings)


def test_load_action_params_no_action_key_direct_model(project):
    job = _job(project, {"epochs": 5})  # no "action" key

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, TrainParams)


# ---------------------------------------------------------------------------
# 7. Multiple validation errors → single exception with all lines
# ---------------------------------------------------------------------------


def test_load_action_params_multiple_errors(project):
    class MultiRequired(BaseModel):
        a: int
        b: int

    job = _job(project, {"action": "s1"})  # both a and b are missing
    bindings = WorkflowBindings().bind("s1", MultiRequired)

    with pytest.raises(TypedParamsValidationError) as exc_info:
        load_action_params(job, "s1", bindings)

    msg = str(exc_info.value)
    assert "s1.a" in msg
    assert "s1.b" in msg


# ---------------------------------------------------------------------------
# Exception chaining
# ---------------------------------------------------------------------------


def test_typed_params_validation_error_chains_original(project):
    job = _job(project, {"action": "train", "lr": 0.01})  # epochs missing
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(TypedParamsValidationError) as exc_info:
        load_action_params(job, "train", bindings)

    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# Reserved SP keys are not passed to the model
# ---------------------------------------------------------------------------


def test_reserved_keys_excluded_from_params(project):
    """action and parent_action must not be passed to the Pydantic model."""

    class OnlyEpochs(BaseModel):
        epochs: int

    job = _job(
        project,
        {"action": "train", "epochs": 5, "parent_action": "abc123def456" * 2},
    )
    bindings = WorkflowBindings().bind("train", OnlyEpochs)

    result = load_action_params(job, "train", bindings)
    assert result.epochs == 5


# ---------------------------------------------------------------------------
# dump_action_params
# ---------------------------------------------------------------------------


def test_dump_action_params_returns_dict(project):
    job = _job(project, {"action": "train", "lr": 0.003, "epochs": 2})
    bindings = WorkflowBindings().bind("train", TrainParams)
    model = load_action_params(job, "train", bindings)

    result = dump_action_params(model)

    assert isinstance(result, dict)
    assert result["lr"] == pytest.approx(0.003)
    assert result["epochs"] == 2
    assert result["batch_size"] == 32


# ---------------------------------------------------------------------------
# New calling styles — bindings form and direct model class form
# ---------------------------------------------------------------------------


def test_load_action_params_bindings_form_infers_action(project):
    """load_action_params(job, bindings) infers action from job.sp['action']."""
    job = _job(project, {"action": "train", "lr": 0.005, "epochs": 4})
    bindings = WorkflowBindings().bind("train", TrainParams)

    result = load_action_params(job, bindings)

    assert isinstance(result, TrainParams)
    assert result.lr == pytest.approx(0.005)
    assert result.epochs == 4
    assert result.batch_size == 32  # default applied


def test_load_action_params_direct_model_class_infers_action(project):
    """load_action_params(job, ModelClass) uses model directly, infers action."""
    job = _job(project, {"action": "train", "lr": 0.002, "epochs": 8})

    result = load_action_params(job, TrainParams)

    assert isinstance(result, TrainParams)
    assert result.lr == pytest.approx(0.002)
    assert result.epochs == 8


def test_load_action_params_direct_class_no_action_key_raises(project):
    """Direct model class form raises ActionParamsNotFoundError when SP has no action."""
    job = _job(project, {"epochs": 5})  # no "action" key

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, TrainParams)


def test_load_action_params_bindings_form_no_action_key_raises(project):
    """Bindings form raises ActionParamsNotFoundError when SP has no action."""
    job = _job(project, {"epochs": 5})  # no "action" key
    bindings = WorkflowBindings().bind("train", TrainParams)

    with pytest.raises(ActionParamsNotFoundError):
        load_action_params(job, bindings)
