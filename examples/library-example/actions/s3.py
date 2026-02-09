import json
from pathlib import Path

import signac
from grubicy import get_parent


def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    assert job.sp["action"] == "s3"
    p3 = job.sp["p3"]

    parent = get_parent(job)
    with open(Path(parent.fn("s2/out.json")), "r", encoding="utf-8") as f:
        s2 = json.load(f)

    value3 = s2["value2"] * p3

    out_path = Path(job.fn("s3/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"p1": s2["p1"], "p2": s2["p2"], "p3": p3, "value3": value3}, f)

    job.doc["s3_value3"] = value3
    job.doc["parent_s2_id"] = parent.id


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
