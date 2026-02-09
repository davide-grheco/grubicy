from pathlib import Path

from signac_deps.row_render import render_row_workflow
from signac_deps.spec import WorkflowSpec


def test_row_render_includes_actions_and_workspace(tmp_path):
    spec = WorkflowSpec.from_mapping(
        {
            "workspace": {"value_file": "signac_statepoint.json"},
            "actions": [
                {"name": "s1", "sp_keys": ["p1"], "outputs": ["s1/out.json"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
            ],
            "experiments": [],
        }
    )

    out_path = render_row_workflow(spec, Path(tmp_path) / "workflow.toml")
    text = out_path.read_text(encoding="utf-8")

    assert 'value_file = "signac_statepoint.json"' in text
    assert 'name = "s1"' in text
    assert 'name = "s2"' in text
    assert 'products = ["s1/out.json"]' in text
