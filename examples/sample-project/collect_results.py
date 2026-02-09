import json
from pathlib import Path

import pandas as pd
import signac


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main():
    project = signac.get_project()

    rows = []
    for j3 in project.find_jobs({"subproject": "s3"}):
        s2_sp = j3.sp["parent_s2"]
        j2 = project.open_job(s2_sp)

        s1_sp = j2.sp["parent_s1"]
        j1 = project.open_job(s1_sp)

        s1_out = read_json(Path(j1.fn("s1/out.json")))
        s2_out = read_json(Path(j2.fn("s2/out.json")))
        s3_out = read_json(Path(j3.fn("s3/out.json")))

        row = {
            "s1_job_id": j1.id,
            "s2_job_id": j2.id,
            "s3_job_id": j3.id,
            "p1": j1.sp.get("p1"),
            "p2": j2.sp.get("p2"),
            "p3": j3.sp.get("p3"),
            "s1_value": s1_out.get("value", j1.doc.get("s1_value")),
            "s2_value2": s2_out.get("value2", j2.doc.get("s2_value2")),
            "s3_value3": s3_out.get("value3", j3.doc.get("s3_value3")),
        }

        rows.append(row)

    df = pd.DataFrame(rows).sort_values(["p1", "p2", "p3"]).reset_index(drop=True)

    df.to_csv("results_table.csv", index=False)

    print(df)
    print(f"\nWrote results_table.csv and results_table.parquet with {len(df)} rows.")


if __name__ == "__main__":
    main()
