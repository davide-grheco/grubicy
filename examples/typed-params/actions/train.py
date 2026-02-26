"""train action — fit a simple model on prepared data.

Reads typed parameters via ``load_action_params`` and writes the fitted
model summary to ``train/model.json``.

Called by row as::

    python actions/train.py {directory}
"""

import json
import math
from pathlib import Path
import sys

from pydantic import BaseModel, Field

from grubicy import get_parent, open_job_from_directory, parent_path
from grubicy.typed import load_action_params


def main(directory: str) -> None:
    job = open_job_from_directory(directory)

    class TrainOptimParams(BaseModel):
        """Optimisation knobs for training."""

        lr: float = Field(default=1e-3, gt=0.0, description="Learning rate.")
        n_iter: int = Field(
            default=100, ge=1, description="Number of training iterations."
        )

    class TrainRegularisationParams(BaseModel):
        """Regularisation controls kept separate on purpose."""

        alpha: float = Field(
            default=0.01, ge=0.0, description="L2 regularisation strength."
        )

    class PrepareParams(BaseModel):
        """Subset of upstream prepare params we care about."""

        noise: float = Field(default=0.1, ge=0.0, le=1.0)
        seed: int = Field(default=42)

    # Load two separate models from the same job state point — demonstrates
    # splitting an action's params across multiple schemas.
    optim = load_action_params(job, TrainOptimParams)
    regularisation = load_action_params(job, TrainRegularisationParams)

    # Also load the parent action's params directly from its job without a registry.
    parent = get_parent(job)
    upstream_params = load_action_params(parent, PrepareParams)

    # Read upstream statistics produced by the prepare action.
    data_path = parent_path(job) / "prepare/data.json"
    data_stats = json.loads(data_path.read_text(encoding="utf-8"))
    variance = data_stats["data_variance"]

    # Simulate gradient descent: loss decays exponentially with lr * n_iter,
    # with a regularisation floor set by alpha.
    final_loss = variance * math.exp(-optim.lr * optim.n_iter) + regularisation.alpha
    score = max(0.0, 1.0 - final_loss)

    result = {
        "lr": optim.lr,
        "n_iter": optim.n_iter,
        "alpha": regularisation.alpha,
        "prepare_noise": upstream_params.noise,
        "prepare_seed": upstream_params.seed,
        "initial_variance": variance,
        "final_loss": final_loss,
        "score": score,
    }

    out = Path(job.fn("train/model.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    job.doc["train_score"] = score
    job.doc["train_loss"] = final_loss
    print(
        f"[train] lr={optim.lr}  n_iter={optim.n_iter}  alpha={regularisation.alpha}"
        f"  (prepare noise={upstream_params.noise}, seed={upstream_params.seed})"
        f"  → loss={final_loss:.6f}  score={score:.4f}"
    )


if __name__ == "__main__":
    main(sys.argv[1])
