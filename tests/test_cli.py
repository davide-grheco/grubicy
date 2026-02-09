import json
from pathlib import Path

import signac

from signac_deps.cli import main


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
            str(config),
            "s1",
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
            "migrate-execute",
            str(config),
            "s1",
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
            str(config),
            "s2",
            "--project",
            str(project.path),
            "--include-doc",
            "--format",
            "json",
        ]
    )


def test_cli_materialize_inits_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = _write_config(tmp_path)

    # No project initialized; CLI should init at --project path.
    main(["materialize", str(config), "--project", str(tmp_path)])

    # Should be able to open the project now.
    proj = signac.Project.get_project(path=tmp_path)
    assert proj is not None
