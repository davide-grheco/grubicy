"""Print a summary table of all evaluate jobs and their scores.

Run from the ``typed-params/`` directory after all actions have completed::

    python collect_results.py
"""

import json
from pathlib import Path

import signac

from grubicy import get_parent


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    project = signac.get_project()

    rows = []
    for j_eval in project.find_jobs({"action": "evaluate"}):
        j_train = get_parent(j_eval)
        j_prepare = get_parent(j_train)

        prepare_out = read_json(Path(j_prepare.fn("prepare/data.json")))
        train_out = read_json(Path(j_train.fn("train/model.json")))
        eval_out = read_json(Path(j_eval.fn("evaluate/report.json")))

        rows.append(
            {
                "n_samples": j_prepare.sp.get("n_samples"),
                "noise": j_prepare.sp.get("noise"),
                "lr": j_train.sp.get("lr"),
                "n_iter": j_train.sp.get("n_iter"),
                "alpha": j_train.sp.get("alpha"),
                "threshold": j_eval.sp.get("threshold"),
                "data_variance": prepare_out.get("data_variance"),
                "final_loss": train_out.get("final_loss"),
                "score": train_out.get("score"),
                "accuracy": eval_out.get("accuracy"),
                "passed": eval_out.get("passed"),
            }
        )

    rows.sort(key=lambda r: (r["noise"], r["lr"], r["n_iter"]))

    # Fixed-width header
    header = f"{'n_samples':>10} {'noise':>6} {'lr':>7} {'n_iter':>7} {'alpha':>6} {'loss':>10} {'score':>7} {'accuracy':>9} {'passed':>6}"
    print(header)
    print("-" * len(header))
    for r in rows:
        passed_str = "yes" if r["passed"] else "no"
        print(
            f"{r['n_samples']:>10} {r['noise']:>6.2f} {r['lr']:>7.4f}"
            f" {r['n_iter']:>7} {r['alpha']:>6.3f}"
            f" {r['final_loss']:>10.6f} {r['score']:>7.4f}"
            f" {r['accuracy']:>9.4f} {passed_str:>6}"
        )

    print(f"\n{len(rows)} experiment(s) collected.")


if __name__ == "__main__":
    main()
