import json
from pathlib import Path

from signac_deps import get_parent, open_job_from_directory, parent_path
from signac_deps.helpers import parent_product_exists


def main(directory: str):
    job = open_job_from_directory(directory)

    assert job.sp["action"] == "s2"
    p2 = job.sp["p2"]

    parent = get_parent(job)
    if not parent_product_exists(job, "s1/out.json"):
        return
    parent_out = parent_path(job) / "s1/out.json"
    with open(parent_out, "r", encoding="utf-8") as f:
        s1 = json.load(f)

    value2 = s1["value"] + p2

    out_path = Path(job.fn("s2/out.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"p1": s1["p1"], "p2": p2, "value2": value2}), encoding="utf-8"
    )

    job.doc["s2_value2"] = value2
    job.doc["parent_s1_id"] = parent.id


if __name__ == "__main__":
    import sys

    main(sys.argv[1])
