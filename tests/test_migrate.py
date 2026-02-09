from pathlib import Path

import json
import pytest
import signac

from signac_deps.materialize import materialize
from signac_deps.migrate import (
    MigrationCollisionError,
    execute_migration,
    plan_migration,
)
from signac_deps.spec import WorkflowSpec


def _spec_three_actions():
    return WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
                {"name": "s3", "sp_keys": ["p3"], "deps": {"action": "s2"}},
            ],
            "experiments": [
                {"s1": {"p1": 1}, "s2": {"p2": 10}, "s3": {"p3": 0.1}},
                {"s1": {"p1": 2}, "s2": {"p2": 10}, "s3": {"p3": 0.1}},
            ],
        }
    )


def test_migration_cascades_downstream(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("test-project")
    spec = _spec_three_actions()

    materialize(spec, project, spec.experiments)

    s1_jobs = list(project.find_jobs({"action": "s1"}))
    s2_jobs = list(project.find_jobs({"action": "s2"}))
    s3_jobs = list(project.find_jobs({"action": "s3"}))

    # Seed a product file to verify it moves with the job rename.
    sample_file = Path(s1_jobs[0].fn("s1/out.json"))
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    sample_file.write_text("{}", encoding="utf-8")

    old_ids = {
        "s1": {j.id for j in s1_jobs},
        "s2": {j.id for j in s2_jobs},
        "s3": {j.id for j in s3_jobs},
    }

    def add_default(sp):
        sp = dict(sp)
        sp.setdefault("b", 0)
        return sp

    plan = plan_migration(spec, project, "s1", add_default)
    report = execute_migration(spec, project, plan)

    assert plan.plan_path and plan.plan_path.exists()
    assert report.updated_actions.get("s1")

    new_s1_jobs = list(project.find_jobs({"action": "s1"}))
    new_s2_jobs = list(project.find_jobs({"action": "s2"}))
    new_s3_jobs = list(project.find_jobs({"action": "s3"}))

    new_ids = {
        "s1": {j.id for j in new_s1_jobs},
        "s2": {j.id for j in new_s2_jobs},
        "s3": {j.id for j in new_s3_jobs},
    }

    assert old_ids["s1"] != new_ids["s1"]
    assert old_ids["s2"] != new_ids["s2"]
    assert old_ids["s3"] != new_ids["s3"]

    # Parent pointers should be updated.
    for job in new_s2_jobs:
        assert job.sp["parent_action"] in new_ids["s1"]
    for job in new_s3_jobs:
        assert job.sp["parent_action"] in new_ids["s2"]

    # Product moved with the renamed job.
    assert any(Path(j.fn("s1/out.json")).exists() for j in new_s1_jobs)

    # Progress log exists
    progress_files = list(
        Path(project.path).glob(".pipeline_migrations/**/progress.json")
    )
    assert progress_files
    progress = json.loads(progress_files[0].read_text())
    assert progress.get("done") is True


def test_migration_plan_detects_collision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("test-project")
    spec = _spec_three_actions()

    materialize(spec, project, spec.experiments)

    def drop_params(sp):
        return {"action": sp["action"]}

    with pytest.raises(MigrationCollisionError):
        plan_migration(spec, project, "s1", drop_params)
