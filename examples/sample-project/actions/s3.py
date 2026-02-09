import json
from pathlib import Path

import signac


def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    assert job.sp["subproject"] == "s3"
    p3 = job.sp["p3"]
    parent_sp = job.sp["parent_s2"]

    parent = project.open_job(parent_sp)

    input_path = Path(parent.fn("s2/out.json"))
    with open(input_path, "r") as f:
        s2 = json.load(f)

    value3 = s2["value2"] * p3

    output_path = Path(job.fn("s3/out.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"p1": s2["p1"], "p2": s2["p2"], "p3": p3, "value3": value3}, f)

    job.doc["s3_value3"] = value3
    job.doc["parent_s2_id"] = parent.id


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
