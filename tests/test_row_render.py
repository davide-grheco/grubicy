import tomllib
from pathlib import Path

from grubicy.row_render import render_row_workflow
from grubicy.spec import WorkflowSpec


def _spec(actions: list, row: dict | None = None) -> WorkflowSpec:
    data: dict = {
        "workspace": {"value_file": "signac_statepoint.json"},
        "actions": actions,
        "experiments": [],
    }
    if row:
        data["row"] = row
    return WorkflowSpec.from_mapping(data)


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def test_row_render_includes_actions_and_workspace(tmp_path):
    spec = _spec(
        [
            {"name": "s1", "sp_keys": ["p1"], "outputs": ["s1/out.json"]},
            {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
        ]
    )

    out_path = render_row_workflow(spec, Path(tmp_path) / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    assert doc["workspace"]["value_file"] == "signac_statepoint.json"
    by_name = {a["name"]: a for a in doc["action"]}
    assert "s1" in by_name
    assert "s2" in by_name
    assert by_name["s1"]["products"] == ["s1/out.json"]


# ---------------------------------------------------------------------------
# previous_actions wiring
# ---------------------------------------------------------------------------


def test_row_render_previous_actions(tmp_path):
    """Dependent actions get previous_actions wired from grubicy deps."""
    spec = _spec(
        [
            {"name": "prepare", "sp_keys": ["seed"], "outputs": ["prepare/done"]},
            {
                "name": "train",
                "sp_keys": ["lr"],
                "outputs": ["train/model.pt"],
                "deps": {"action": "prepare"},
            },
            {
                "name": "eval",
                "sp_keys": ["metric"],
                "outputs": ["eval/result.json"],
                "deps": {"action": "train"},
            },
        ]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    by_name = {a["name"]: a for a in doc["action"]}
    assert "previous_actions" not in by_name["prepare"]
    assert by_name["train"]["previous_actions"] == ["prepare"]
    assert by_name["eval"]["previous_actions"] == ["train"]


def test_row_render_root_action_has_no_previous_actions(tmp_path):
    spec = _spec([{"name": "root", "sp_keys": ["x"]}])
    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert "previous_actions" not in doc["action"][0]


# ---------------------------------------------------------------------------
# resources pass-through
# ---------------------------------------------------------------------------


def test_row_render_resources(tmp_path):
    spec = _spec(
        [
            {
                "name": "sim",
                "sp_keys": ["n"],
                "resources": {
                    "walltime": {"per_directory": "02:00:00"},
                    "threads_per_process": 8,
                },
            }
        ]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    res = doc["action"][0]["resources"]
    assert res["threads_per_process"] == 8
    assert res["walltime"]["per_directory"] == "02:00:00"


def test_row_render_no_resources_key_when_empty(tmp_path):
    spec = _spec([{"name": "s1", "sp_keys": ["p"]}])
    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert "resources" not in doc["action"][0]


# ---------------------------------------------------------------------------
# submit_options pass-through
# ---------------------------------------------------------------------------


def test_row_render_submit_options(tmp_path):
    spec = _spec(
        [
            {
                "name": "dock",
                "sp_keys": ["ligand"],
                "submit_options": {
                    "ft3": {
                        "account": "mylab",
                        "setup": "module load python/3.11",
                        "custom": ["--mem-per-cpu=4000M"],
                        "output_file_path": "row_logs",
                    }
                },
            }
        ]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    ft3 = doc["action"][0]["submit_options"]["ft3"]
    assert ft3["account"] == "mylab"
    assert ft3["custom"] == ["--mem-per-cpu=4000M"]
    assert ft3["output_file_path"] == "row_logs"


# ---------------------------------------------------------------------------
# group.maximum_size / submit_whole
# ---------------------------------------------------------------------------


def test_row_render_group_maximum_size(tmp_path):
    spec = _spec(
        [{"name": "s1", "sp_keys": ["p"], "group": {"maximum_size": 4}}]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    assert doc["action"][0]["group"]["maximum_size"] == 4


def test_row_render_group_default_maximum_size_is_1(tmp_path):
    """When group.maximum_size is not set, the renderer must emit maximum_size=1.

    Without an explicit limit, Row bundles every matching directory into a
    single SLURM job.  One directory per job is the only safe default for
    heterogeneous HPC workloads.
    """
    spec = _spec([{"name": "s1", "sp_keys": ["p"]}])  # no group section at all

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    assert doc["action"][0]["group"]["maximum_size"] == 1


def test_row_render_group_submit_whole(tmp_path):
    spec = _spec(
        [{"name": "agg", "sp_keys": ["run"], "group": {"submit_whole": True}}]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    assert doc["action"][0]["group"]["submit_whole"] is True
    # maximum_size must still be present (defaulting to 1)
    assert doc["action"][0]["group"]["maximum_size"] == 1


def test_row_render_group_always_has_include_filter(tmp_path):
    spec = _spec([{"name": "s1", "sp_keys": ["p"], "group": {"maximum_size": 2}}])

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    include = doc["action"][0]["group"]["include"]
    assert include[0]["condition"] == ["/action", "==", "s1"]


# ---------------------------------------------------------------------------
# [default.action] from [row.default.action] in pipeline config
# ---------------------------------------------------------------------------


def test_row_render_default_action_block(tmp_path):
    spec = _spec(
        [{"name": "s1", "sp_keys": ["p"]}],
        row={
            "default": {
                "action": {
                    "submit_options": {
                        "ft3": {
                            "account": "mylab",
                            "setup": "module load miniforge3/24.1.2-0",
                        }
                    }
                }
            }
        },
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))

    assert doc["default"]["action"]["submit_options"]["ft3"]["account"] == "mylab"


def test_row_render_no_default_block_when_absent(tmp_path):
    spec = _spec([{"name": "s1", "sp_keys": ["p"]}])
    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert "default" not in doc


# ---------------------------------------------------------------------------
# Topological order
# ---------------------------------------------------------------------------


def test_row_render_topological_order(tmp_path):
    """Actions appear in dependency order in the generated file."""
    spec = _spec(
        [
            {"name": "c", "sp_keys": [], "deps": {"action": "b"}},
            {"name": "a", "sp_keys": []},
            {"name": "b", "sp_keys": [], "deps": {"action": "a"}},
        ]
    )

    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    names = [a["name"] for a in doc["action"]]
    assert names.index("a") < names.index("b") < names.index("c")


# ---------------------------------------------------------------------------
# Custom default_command and runner override
# ---------------------------------------------------------------------------


def test_row_render_custom_default_command(tmp_path):
    spec = _spec([{"name": "run", "sp_keys": ["x"]}])
    out_path = render_row_workflow(
        spec,
        tmp_path / "workflow.toml",
        default_command="python runner.py --action {name} {directory}",
    )
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert doc["action"][0]["command"] == "python runner.py --action run {directory}"


def test_row_render_runner_overrides_default_command(tmp_path):
    spec = _spec(
        [{"name": "run", "sp_keys": ["x"], "runner": "bash scripts/run.sh {directory}"}]
    )
    out_path = render_row_workflow(spec, tmp_path / "workflow.toml")
    doc = tomllib.loads(out_path.read_text(encoding="utf-8"))
    assert doc["action"][0]["command"] == "bash scripts/run.sh {directory}"
