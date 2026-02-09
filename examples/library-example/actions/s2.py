import json
from pathlib import Path

import signac
from signac_deps import get_parent


def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    assert job.sp["action"] == "s2"
    p2 = job.sp["p2"]

    parent = get_parent(job)
    with open(Path(parent.fn("s1/out.json")), "r", encoding="utf-8") as f:
        s1 = json.load(f)

    value2 = s1["value"] + p2

    out_path = Path(job.fn("s2/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"p1": s1["p1"], "p2": p2, "value2": value2}, f)

    job.doc["s2_value2"] = value2
    job.doc["parent_s1_id"] = parent.id


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
