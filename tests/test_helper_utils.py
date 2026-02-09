import json
from pathlib import Path

import signac

from grubicy.helpers import (
    get_parent,
    get_parent_doc,
    open_job_from_directory,
    parent_product_exists,
)


def test_job_json_helpers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = signac.init_project("helpers")

    parent = project.open_job({"action": "s1", "p1": 1})
    parent.init()
    out_path = Path(parent.fn("s1/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"value": 2}), encoding="utf-8")

    child = project.open_job({"action": "s2", "p2": 3, "parent_action": parent.id})
    child.init()

    reopened = open_job_from_directory(child.path)
    assert reopened.id == child.id

    s1 = json.loads(out_path.read_text())
    assert s1["value"] == 2

    assert get_parent(child).id == parent.id
    assert get_parent_doc(child, "missing", default=5) == 5
    assert parent_product_exists(child, "s1/out.json") is True
    assert parent_product_exists(child, "missing.json") is False
