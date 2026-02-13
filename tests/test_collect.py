import pytest
import signac

from grubicy.collect import collect_params_with_parents
from grubicy.materialize import materialize
from grubicy.spec import WorkflowSpec


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


def test_collect_flattens_params_and_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("collect-project")
    spec = _spec_two_actions()

    materialize(spec, project, spec.experiments)

    s1 = next(iter(project.find_jobs({"action": "s1"})))
    s2 = next(iter(project.find_jobs({"action": "s2"})))

    s1.doc["result"] = 4
    s2.doc["metric"] = 9
    s2.doc["pipeline"] = "skip-me"

    rows = collect_params_with_parents(
        spec, project, "s2", include_doc=True, missing_ok=False
    )

    assert len(rows) == 1
    data = rows[0].data
    assert data["s1.p1"] == 1
    assert data["s2.p2"] == 2
    assert data["s1.doc.result"] == 4
    assert data["s2.doc.metric"] == 9
    assert "s2.doc.pipeline" not in data


def test_collect_raises_when_parent_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("collect-project")
    spec = _spec_two_actions()

    # Create a child job without a parent pointer.
    job = project.open_job({"action": "s2", "p2": 2})
    job.init()

    with pytest.raises(LookupError):
        collect_params_with_parents(spec, project, "s2", include_doc=False)


def test_collect_missing_ok_skips_missing_parents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("collect-project")
    spec = _spec_two_actions()

    job = project.open_job({"action": "s2", "p2": 2})
    job.init()

    rows = collect_params_with_parents(
        spec, project, "s2", include_doc=False, missing_ok=True
    )

    assert rows == []
