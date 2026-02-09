import pytest

from grubicy.spec import ConfigValidationError, WorkflowSpec


def test_topological_order_and_experiments():
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
                {"name": "s3", "sp_keys": ["p3"], "deps": {"action": "s2"}},
            ],
            "experiments": [
                {"s1": {"p1": 1}, "s2": {"p2": 2}, "s3": {"p3": 3}},
            ],
        }
    )

    order = [a.name for a in spec.topological_actions()]

    assert order == ["s1", "s2", "s3"]
    assert len(spec.experiments) == 1
    assert spec.experiments[0]["s1"]["p1"] == 1


def test_cycle_detection_raises():
    with pytest.raises(ConfigValidationError):
        WorkflowSpec.from_mapping(
            {
                "actions": [
                    {"name": "a", "sp_keys": [], "deps": {"action": "b"}},
                    {"name": "b", "sp_keys": [], "deps": {"action": "a"}},
                ]
            }
        )
