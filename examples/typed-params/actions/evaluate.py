"""evaluate action — assess model quality against a threshold.

Reads typed parameters via ``load_action_params`` and writes evaluation
metrics to ``evaluate/report.json``.

Called by row as::

    python actions/evaluate.py {directory}
"""

import json
from pathlib import Path

import sys

from pydantic import BaseModel, Field

from grubicy import open_job_from_directory, parent_path
from grubicy.typed import WorkflowBindings, load_action_params


def main(directory: str) -> None:
    job = open_job_from_directory(directory)

    class EvaluateParams(BaseModel):
        """Parameters for the *evaluate* action."""

        threshold: float = Field(
            default=0.5,
            ge=0.0,
            le=1.0,
            description="Minimum score to consider the run successful.",
        )
    bindings = WorkflowBindings().bind("evaluate", EvaluateParams)

    # threshold is a float with ge=0, le=1 enforced by Pydantic.
    params = load_action_params(job, bindings)

    model_path = parent_path(job) / "train/model.json"
    model = json.loads(model_path.read_text(encoding="utf-8"))
    score = model["score"]

    passed = score >= params.threshold
    # Accuracy mirrors the score when above threshold, penalised below it.
    accuracy = score if passed else score * (score / params.threshold)

    result = {
        "threshold": params.threshold,
        "score": score,
        "accuracy": accuracy,
        "passed": passed,
    }

    out = Path(job.fn("evaluate/report.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    job.doc["eval_accuracy"] = accuracy
    job.doc["eval_passed"] = passed
    status = "PASS" if passed else "FAIL"
    print(
        f"[evaluate] threshold={params.threshold}  score={score:.4f}"
        f"  accuracy={accuracy:.4f}  [{status}]"
    )


if __name__ == "__main__":
    main(sys.argv[1])
