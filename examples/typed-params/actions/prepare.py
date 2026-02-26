"""prepare action — generate synthetic data.

Reads typed parameters via ``load_action_params`` and writes summary
statistics to ``prepare/data.json``.

Called by row as::

    python actions/prepare.py {directory}
"""

import json
import math
import random
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from grubicy import open_job_from_directory
from grubicy.typed import WorkflowBindings, load_action_params



def main(directory: str) -> None:
    job = open_job_from_directory(directory)

    class PrepareParams(BaseModel):
        """Parameters for the *prepare* action."""

        n_samples: int = Field(
            ge=10, description="Number of synthetic data points to generate."
        )
        noise: float = Field(
            default=0.1,
            ge=0.0,
            le=1.0,
            description="Standard deviation of the additive Gaussian noise.",
        )
        seed: int = Field(default=42, description="Random seed for reproducibility.")

    bindings = WorkflowBindings().bind("prepare", PrepareParams)

    # Load and validate all parameters for this action in one call.
    # `params` is a fully typed PrepareParams instance — IDE autocomplete works,
    # constraints are enforced, and missing required fields raise immediately.
    params = load_action_params(job, bindings)

    rng = random.Random(params.seed)
    samples = [rng.gauss(0, params.noise) for _ in range(params.n_samples)]

    mean = sum(samples) / params.n_samples
    variance = sum((x - mean) ** 2 for x in samples) / params.n_samples
    std = math.sqrt(variance)

    result = {
        "n_samples": params.n_samples,
        "noise": params.noise,
        "seed": params.seed,
        "mean": mean,
        "std": std,
        "data_variance": variance,
    }

    out = Path(job.fn("prepare/data.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    job.doc["prepare_mean"] = mean
    job.doc["prepare_std"] = std
    print(
        f"[prepare] n_samples={params.n_samples}  noise={params.noise}  variance={variance:.6f}"
    )


if __name__ == "__main__":
    main(sys.argv[1])
