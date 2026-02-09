from pathlib import Path

import pytest
import signac

from signac_deps.helpers import DependencyResolutionError, get_parent, parent_file
from signac_deps.materialize import materialize
from signac_deps.spec import ConfigValidationError, WorkflowSpec


def _spec_two_actions():
    return WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": ["p1"]},
                {"name": "s2", "sp_keys": ["p2"], "deps": {"action": "s1"}},
            ],
            "experiments": [
                {"s1": {"p1": 1}, "s2": {"p2": 2}},
            ],
        }
    )


def test_materialize_creates_parent_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("test-project")
    spec = _spec_two_actions()

    report = materialize(spec, project, spec.experiments)

    assert report.created == 2
    assert report.total == 2
    assert set(report.per_action) == {"s1", "s2"}

    s1_jobs = list(project.find_jobs({"action": "s1"}))
    s2_jobs = list(project.find_jobs({"action": "s2"}))
    assert len(s1_jobs) == 1
    assert len(s2_jobs) == 1

    s1 = s1_jobs[0]
    s2 = s2_jobs[0]

    assert s2.sp["parent_action"] == s1.id
    assert s2.doc["deps_meta"]["s1"]["job_id"] == s1.id


def test_materialize_rejects_unknown_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("test-project")
    spec = _spec_two_actions()

    experiments = [{"s1": {"p1": 1, "extra": 5}, "s2": {"p2": 2}}]

    with pytest.raises(ConfigValidationError):
        materialize(spec, project, experiments)


def test_parent_helpers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("test-project")
    spec = _spec_two_actions()

    materialize(spec, project, spec.experiments)

    s1 = next(iter(project.find_jobs({"action": "s1"})))
    s2 = next(iter(project.find_jobs({"action": "s2"})))

    out_path = Path(s1.fn("s1/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("{}", encoding="utf-8")

    parent = get_parent(s2)
    assert parent.id == s1.id

    resolved = parent_file(s2, "s1/out.json")
    assert resolved == out_path

    with pytest.raises(DependencyResolutionError):
        _ = get_parent(s1)
