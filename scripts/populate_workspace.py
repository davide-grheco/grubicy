"""Populate the signac workspace for the demo.

Creates one signac job per (protein, ligand, param_set_id, replica_seed).
"""

from __future__ import annotations

import csv
from pathlib import Path

import signac

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PARAM_SET_DIR = PROJECT_ROOT / "configs" / "param-sets"
LIGAND_TABLE = PROJECT_ROOT / "inputs" / "ligands.csv"

# For the demo we use 2 replicates to test seeding.
REPLICA_SEEDS = [0, 1]


def main() -> None:
    project = signac.get_project()

    # Discover available parameter sets
    param_set_ids = sorted([p.stem for p in PARAM_SET_DIR.glob("*.json")])
    if not param_set_ids:
        raise RuntimeError(f"No parameter sets found in {PARAM_SET_DIR}")

    with open(LIGAND_TABLE, newline="") as f:
        rows = list(csv.DictReader(f))

    n_created = 0
    for row in rows:
        for ps_id in param_set_ids:
            for seed in REPLICA_SEEDS:
                sp = {
                    "protein_id": row["protein_id"],
                    "ligand_id": row["ligand_id"],
                    "param_set_id": ps_id,
                    "engine": "gromacs",
                    "replica_seed": seed,
                }
                job = project.open_job(sp).init()
                n_created += 1

    print(f"Created/initialized {n_created} jobs.")


if __name__ == "__main__":
    main()
