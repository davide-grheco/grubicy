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


def test_grid_cartesian_product():
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
            ],
            "grid": [{"s1": {"p1": [1, 2, 3]}, "s2": {"p2": [10, 20]}}],
        }
    )

    exps = spec.experiments
    assert len(exps) == 6
    pairs = {(e["s1"]["p1"], e["s2"]["p2"]) for e in exps}
    assert pairs == {(1, 10), (1, 20), (2, 10), (2, 20), (3, 10), (3, 20)}


def test_grid_scalar_params_fixed():
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [{"name": "s1", "sp_keys": ["p1", "fixed"]}],
            "grid": [{"s1": {"p1": [1, 2], "fixed": "x"}}],
        }
    )

    exps = spec.experiments
    assert len(exps) == 2
    assert all(e["s1"]["fixed"] == "x" for e in exps)
    assert {e["s1"]["p1"] for e in exps} == {1, 2}


def test_grid_multiple_blocks_concatenated():
    # Dependent case: p1=1 allows p2=[10,20], p1=2 allows p2=[30]
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
            ],
            "grid": [
                {"s1": {"p1": [1]}, "s2": {"p2": [10, 20]}},
                {"s1": {"p1": [2]}, "s2": {"p2": [30]}},
            ],
        }
    )

    exps = spec.experiments
    assert len(exps) == 3
    pairs = {(e["s1"]["p1"], e["s2"]["p2"]) for e in exps}
    assert pairs == {(1, 10), (1, 20), (2, 30)}


def test_grid_and_experiment_cross_product():
    # Grid covers s1+s2; experiments vary s3 — total = grid_combos × experiments
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
                {"name": "s3", "sp_keys": ["p3"], "deps": {"action": "s2"}},
            ],
            "grid": [{"s1": {"p1": [1, 2]}, "s2": {"p2": [10, 20]}}],
            "experiment": [{"s3": {"p3": 0.1}}, {"s3": {"p3": 0.2}}],
        }
    )

    # 2 p1 × 2 p2 = 4 grid combos × 2 experiments = 8 total
    assert len(spec.experiments) == 8
    assert {e["s3"]["p3"] for e in spec.experiments} == {0.1, 0.2}
    assert {e["s1"]["p1"] for e in spec.experiments} == {1, 2}
    assert {e["s2"]["p2"] for e in spec.experiments} == {10, 20}


def test_experiment_applies_named_grids_only():
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
                {"name": "s3", "sp_keys": ["p3"], "deps": {"action": "s2"}},
            ],
            "grid": [
                {"name": "low", "s1": {"p1": [1]}, "s2": {"p2": [1, 2, 3, 4]}},
                {"name": "high", "s1": {"p1": [2]}, "s2": {"p2": [5, 6, 7, 8]}},
            ],
            "experiment": [
                {"s3": {"p3": 1}},                   # all grids → 8 combos
                {"grids": ["low"], "s3": {"p3": 2}},  # only "low" → 4 combos
            ],
        }
    )

    assert len(spec.experiments) == 12
    # p3=1 experiments all come from both grids
    p3_1 = [e for e in spec.experiments if e["s3"]["p3"] == 1]
    assert len(p3_1) == 8
    assert {e["s1"]["p1"] for e in p3_1} == {1, 2}
    # p3=2 experiments only come from "low"
    p3_2 = [e for e in spec.experiments if e["s3"]["p3"] == 2]
    assert len(p3_2) == 4
    assert {e["s1"]["p1"] for e in p3_2} == {1}


def test_experiment_opts_out_of_grids():
    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
            ],
            "grid": [{"name": "base", "s2": {"p2": [10, 20, 30]}}],
            "experiment": [
                {"s1": {"p1": 1}},             # uses all grids → 3 combos
                {"grids": [], "s1": {"p1": 2}},  # standalone → 1 combo
            ],
        }
    )

    assert len(spec.experiments) == 4
    standalone = [e for e in spec.experiments if e["s1"]["p1"] == 2]
    assert len(standalone) == 1
    assert "s2" not in standalone[0]


def test_experiment_unknown_grid_name_raises():
    with pytest.raises(ConfigValidationError, match="unknown grid 'typo'"):
        WorkflowSpec.from_mapping(
            {
                "actions": [{"name": "s1", "sp_keys": ["p1"]}],
                "grid": [{"name": "base", "s1": {"p1": [1, 2]}}],
                "experiment": [{"grids": ["typo"], "s1": {"p1": 99}}],
            }
        )


def test_grid_unknown_action_raises():
    with pytest.raises(ConfigValidationError, match="Unnamed grid references unknown action 'typo'"):
        WorkflowSpec.from_mapping(
            {
                "actions": [{"name": "s1", "sp_keys": ["p1"]}],
                "grid": [{"typo": {"p1": [1, 2]}}],
            }
        )


def test_experiment_unknown_action_raises():
    with pytest.raises(ConfigValidationError, match="unknown action 'ghost'"):
        WorkflowSpec.from_mapping(
            {
                "actions": [{"name": "s1", "sp_keys": ["p1"]}],
                "experiment": [{"ghost": {"p1": 1}}],
            }
        )


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
