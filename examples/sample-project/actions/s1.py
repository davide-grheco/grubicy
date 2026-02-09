import json
from pathlib import Path

import signac


def main(directory: str):
    project = signac.get_project()
    job = project.open_job(id=Path(directory).name)

    assert job.sp["subproject"] == "s1"
    p1 = job.sp["p1"]

    value = p1 * p1

    out_path = Path(job.fn("s1/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"p1": p1, "value": value}, f)

    job.doc["s1_value"] = value


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
