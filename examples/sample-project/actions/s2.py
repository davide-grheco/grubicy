import json
from pathlib import Path

import signac


def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    assert job.sp["subproject"] == "s2"
    p2 = job.sp["p2"]
    parent_sp = job.sp["parent_s1"]

    parent = project.open_job(parent_sp)

    input_path = Path(parent.fn("s1/out.json"))
    with open(input_path, "r") as f:
        s1 = json.load(f)

    value2 = s1["value"] + p2

    output_path = Path(job.fn("s2/out.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"p1": s1["p1"], "p2": p2, "value2": value2}, f)

    job.doc["s2_value2"] = value2
    job.doc["parent_s1_id"] = parent.id


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
