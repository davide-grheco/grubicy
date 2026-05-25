import json
from pathlib import Path

import pytest
import signac
import tomllib

from grubicy.cli import _find_config, main


def _write_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "pipeline.toml"
    cfg.write_text(
        """
[workspace]
value_file = "signac_statepoint.json"

[[actions]]
name = "s1"
sp_keys = ["p1"]
outputs = ["s1/out.json"]

[[actions]]
name = "s2"
sp_keys = ["p2"]
deps = { action = "s1" }
outputs = ["s2/out.json"]

[[experiment]]
  [experiment.s1]
  p1 = 1
  [experiment.s2]
  p2 = 2
""",
        encoding="utf-8",
    )
    return cfg


def test_cli_materialize_and_render(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)
    project = signac.init_project("cli-project")

    main(["validate", str(config)])
    main(["materialize", str(config), "--project", str(project.path)])
    main(["render-row", str(config), "--output", "workflow.toml"])

    out = Path("workflow.toml")
    assert out.exists()


def test_cli_migration_plan_and_execute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)
    project = signac.init_project("cli-project")
    main(["materialize", str(config), "--project", str(project.path)])

    main(
        [
            "migrate-plan",
            "s1",
            "--config",
            str(config),
            "--project",
            str(project.path),
            "--setdefault",
            "b=0",
        ]
    )

    plans = list(
        Path(project.path).joinpath(".pipeline_migrations").glob("plan_*.json")
    )
    assert plans

    plan_path = plans[0]
    main(
        [
            "migrate-apply",
            "s1",
            "--config",
            str(config),
            "--project",
            str(project.path),
            "--plan",
            str(plan_path),
        ]
    )

    progress_files = list(
        Path(project.path).joinpath(".pipeline_migrations").glob("run_*/progress.json")
    )
    assert progress_files
    progress = json.loads(progress_files[0].read_text())
    assert progress.get("done") is True


def test_cli_collect_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)
    project = signac.init_project("cli-project")
    main(["materialize", str(config), "--project", str(project.path)])

    s1 = next(iter(project.find_jobs({"action": "s1"})))
    s1.doc["result"] = 4

    main(
        [
            "collect-params",
            "s2",
            "--config",
            str(config),
            "--project",
            str(project.path),
            "--include-doc",
            "--format",
            "json",
        ]
    )


def test_cli_migrate_plan_updates_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)
    project = signac.init_project("cli-project")
    main(["materialize", str(config), "--project", str(project.path)])

    main(
        [
            "migrate-plan",
            "s2",
            "--config",
            str(config),
            "--project",
            str(project.path),
            "--setdefault",
            "test=6",
        ]
    )

    cfg = tomllib.loads(Path(config).read_text(encoding="utf-8"))
    s2_block = cfg["actions"][1]
    assert "test" in s2_block.get("sp_keys", [])
    for exp in cfg.get("experiment", []):
        assert exp.get("s2", {}).get("test") == "6"


def test_cli_materialize_inits_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)

    # No project initialized; CLI should init at --project path.
    main(["materialize", str(config), "--project", str(tmp_path)])

    # Should be able to open the project now.
    proj = signac.Project.get_project(path=tmp_path)
    assert proj is not None


def test_get_or_init_project_does_not_walk_up(tmp_path, monkeypatch):
    """_get_or_init_project must not find a project in a parent directory."""
    from grubicy.cli import _get_or_init_project

    # Init a signac project in tmp_path (the parent).
    signac.init_project(path=str(tmp_path))

    # Change into a subdirectory that has no signac project.
    subdir = tmp_path / "sub"
    subdir.mkdir()
    monkeypatch.chdir(subdir)

    # Old code (signac.get_project()) would have found the parent's project.
    # The fix should create a new project in CWD instead.
    project = _get_or_init_project()
    assert Path(project.path).resolve() == subdir.resolve()


# ---------------------------------------------------------------------------
# Auto-detection tests
# ---------------------------------------------------------------------------


def test_find_config_cwd(tmp_path, monkeypatch):
    """_find_config returns a pipeline.toml in the CWD."""
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "pipeline.toml"
    cfg.write_text("[workspace]\n", encoding="utf-8")
    assert _find_config() == cfg


def test_find_config_walks_up(tmp_path, monkeypatch):
    """_find_config walks up to a parent directory."""
    cfg = tmp_path / "pipeline.toml"
    cfg.write_text("[workspace]\n", encoding="utf-8")
    subdir = tmp_path / "sub" / "subsub"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    assert _find_config() == cfg


def test_find_config_prefers_toml_over_yaml(tmp_path, monkeypatch):
    """pipeline.toml is preferred over pipeline.yaml when both exist."""
    monkeypatch.chdir(tmp_path)
    toml = tmp_path / "pipeline.toml"
    yaml = tmp_path / "pipeline.yaml"
    toml.write_text("[workspace]\n", encoding="utf-8")
    yaml.write_text("workspace: {}\n", encoding="utf-8")
    assert _find_config() == toml


def test_find_config_returns_none_when_missing(tmp_path, monkeypatch):
    """_find_config returns None when no pipeline config exists anywhere."""
    monkeypatch.chdir(tmp_path)
    assert _find_config() is None


def test_cli_auto_detect_config(tmp_path, monkeypatch):
    """Commands work without an explicit config when pipeline.toml is in CWD."""
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    project = signac.init_project("auto-project")

    # validate should find the config automatically
    main(["validate"])

    # materialize should find the config automatically
    main(["materialize", "--project", str(project.path)])


def test_cli_auto_detect_config_missing(tmp_path, monkeypatch):
    """A clear error is raised when no config is found and none is given."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="No config file found"):
        main(["validate"])
