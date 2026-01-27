"""Row actions for the GBSA study demo.

Each action reads the correct protein/ligand/param_set inputs and writes small output
files + a few fields into job.doc.

IMPORTANT: Outputs are deterministic random numbers seeded by
(protein_id, ligand_id, param_set_id, replica_seed, action_name) so the demo
is reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import signac

PROJECT_ROOT = Path(__file__).resolve().parent
INPUTS = PROJECT_ROOT / "inputs"
PROTEIN_DIR = INPUTS / "proteins"
LIGAND_TABLE = INPUTS / "ligands.csv"
PARAM_SET_DIR = PROJECT_ROOT / "configs" / "param-sets"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_seed(*parts: str) -> int:
    h = hashlib.sha256(("|".join(parts)).encode("utf-8")).digest()
    # Use 8 bytes for a deterministic int seed.
    return int.from_bytes(h[:8], "big", signed=False)


def _load_ligand_table() -> Dict[Tuple[str, str], Dict[str, Any]]:
    # Lightweight CSV parse without pandas to keep deps minimal.
    import csv

    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    with open(LIGAND_TABLE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["protein_id"], row["ligand_id"])
            row2 = dict(row)
            # Convert numerics
            if "Ki_nM" in row2 and row2["Ki_nM"] != "":
                row2["Ki_nM"] = float(row2["Ki_nM"])
            out[key] = row2
    return out


def _load_param_sets() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in sorted(PARAM_SET_DIR.glob("*.json")):
        ps_id = path.stem
        out[ps_id] = json.loads(path.read_text())
    return out


def _ensure_parent(job, relpath: str) -> None:
    Path(job.fn(relpath)).parent.mkdir(parents=True, exist_ok=True)


def _write_product_atomic(job, relpath: str, payload: Dict[str, Any]) -> None:
    _ensure_parent(job, relpath)
    tmp = job.fn(relpath + ".in_progress")
    final = job.fn(relpath)
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, final)


def _read_protein_pdb(protein_id: str) -> str:
    path = PROTEIN_DIR / f"{protein_id}.pdb"
    return path.read_text()


def _job_context(job) -> Dict[str, Any]:
    sp = job.cached_statepoint
    return {
        "protein_id": sp["protein_id"],
        "ligand_id": sp["ligand_id"],
        "param_set_id": sp["param_set_id"],
        "engine": sp.get("engine", "gromacs"),
        "replica_seed": sp.get("replica_seed", 0),
    }


def ligand_param(*jobs):
    ligand_rows = _load_ligand_table()
    param_sets = _load_param_sets()

    for job in jobs:
        if job.isfile("ligparam/ligparam.json"):
            continue

        ctx = _job_context(job)
        key = (ctx["protein_id"], ctx["ligand_id"])
        lig = ligand_rows[key]
        params = param_sets[ctx["param_set_id"]]

        # Read protein file to demonstrate file picking
        pdb_text = _read_protein_pdb(ctx["protein_id"])
        protein_hash = _sha256_bytes(pdb_text.encode("utf-8"))

        # Deterministic random-ish "charge_model_score"
        seed = _stable_seed(
            ctx["protein_id"],
            ctx["ligand_id"],
            ctx["param_set_id"],
            str(ctx["replica_seed"]),
            "ligand_param",
        )
        # Create a pseudo-random value without importing numpy
        score = (seed % 10_000) / 10_000.0

        payload = {
            "protein_hash": protein_hash,
            "smiles": lig["smiles"],
            "param_set_id": ctx["param_set_id"],
            "param_set_hash": _sha256_bytes(
                json.dumps(params, sort_keys=True).encode("utf-8")
            ),
            "ligparam_score": score,
            "timestamp": time.time(),
        }
        _write_product_atomic(job, "ligparam/ligparam.json", payload)

        job.doc["param_set_id"] = ctx["param_set_id"]
        job.doc["param_set_hash"] = payload["param_set_hash"]
        job.doc["ligparam_score"] = score
        job.doc["protein_hash"] = protein_hash


def docking(*jobs):
    ligand_rows = _load_ligand_table()
    for job in jobs:
        if job.isfile("dock/dock.json"):
            continue
        ctx = _job_context(job)
        lig = ligand_rows[(ctx["protein_id"], ctx["ligand_id"])]

        # deterministic "docking_score"
        seed = _stable_seed(
            ctx["protein_id"],
            ctx["ligand_id"],
            ctx["param_set_id"],
            str(ctx["replica_seed"]),
            "docking",
        )
        dock_score = -(seed % 8000) / 1000.0  # negative is "better"

        payload = {
            "smiles": lig["smiles"],
            "dock_score": dock_score,
            "timestamp": time.time(),
        }
        _write_product_atomic(job, "dock/dock.json", payload)
        job.doc["dock_score"] = dock_score


def md(*jobs):
    # Dummy MD: records pretend runtime + stability flag
    for job in jobs:
        if job.isfile("md/md.json"):
            continue
        ctx = _job_context(job)

        seed = _stable_seed(
            ctx["protein_id"],
            ctx["ligand_id"],
            ctx["param_set_id"],
            str(ctx["replica_seed"]),
            "md",
        )
        # Fake runtime in seconds
        runtime_s = 1.0 + (seed % 2000) / 1000.0
        stable = (seed % 20) != 0  # ~5% unstable

        payload = {
            "runtime_s": runtime_s,
            "stable": stable,
            "timestamp": time.time(),
        }
        _write_product_atomic(job, "md/md.json", payload)
        job.doc["md_runtime_s"] = runtime_s
        job.doc["md_stable"] = stable


def gbsa(*jobs):
    # Dummy GBSA: generates a predicted ΔG.
    for job in jobs:
        if job.isfile("gbsa/gbsa.json"):
            continue
        ctx = _job_context(job)

        seed = _stable_seed(
            ctx["protein_id"],
            ctx["ligand_id"],
            ctx["param_set_id"],
            str(ctx["replica_seed"]),
            "gbsa",
        )
        # Fake ΔG in kcal/mol
        dg = -5.0 - (seed % 8000) / 1000.0

        payload = {"dg_pred_kcal_mol": dg, "timestamp": time.time()}
        _write_product_atomic(job, "gbsa/gbsa.json", payload)
        job.doc["dg_pred_kcal_mol"] = dg


def metrics(*jobs):
    ligand_rows = _load_ligand_table()
    for job in jobs:
        if job.isfile("metrics/metrics.json"):
            continue
        ctx = _job_context(job)
        lig = ligand_rows[(ctx["protein_id"], ctx["ligand_id"])]

        # Convert Ki_nM to pKi for a toy "ground truth"
        ki_nM = lig.get("Ki_nM", None)
        pki = None
        if isinstance(ki_nM, (int, float)) and ki_nM > 0:
            # Ki_M = Ki_nM * 1e-9; pKi = -log10(Ki_M)
            import math

            pki = -math.log10(ki_nM * 1e-9)

        dg = job.doc.get("dg_pred_kcal_mol", None)
        stable = job.doc.get("md_stable", True)

        payload = {
            "protein_id": ctx["protein_id"],
            "ligand_id": ctx["ligand_id"],
            "param_set_id": ctx["param_set_id"],
            "replica_seed": ctx["replica_seed"],
            "dg_pred_kcal_mol": dg,
            "Ki_nM": ki_nM,
            "pKi": pki,
            "label": lig.get("label"),
            "md_stable": stable,
            "timestamp": time.time(),
        }
        _write_product_atomic(job, "metrics/metrics.json", payload)

        # Store a few key fields in job.doc for querying/aggregation
        job.doc["Ki_nM"] = ki_nM
        job.doc["pKi"] = pki
        job.doc["label"] = lig.get("label")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True)
    parser.add_argument("directories", nargs="+")
    args = parser.parse_args()

    project = signac.get_project()
    jobs = [project.open_job(id=d) for d in args.directories]

    fn = globals().get(args.action)
    if fn is None:
        raise SystemExit(f"Unknown action: {args.action}")
    fn(*jobs)
