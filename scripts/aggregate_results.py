"""Aggregate results by parameter set.

Reads job.doc fields via signac, builds DataFrames, and computes toy metrics:
- Spearman correlation between predicted dg and pKi within each protein
- Aggregate mean Spearman across proteins per param_set_id
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import signac

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    project = signac.get_project()

    # Export state points + job document to a DataFrame.
    # Requires pandas installed.
    df = project.to_dataframe()
    if df.empty:
        print("No jobs found. Did you run populate_workspace.py?")
        return

    # Keep only rows with computed predictions/targets
    cols_needed = ["protein_id", "ligand_id", "param_set_id", "replica_seed", "dg_pred_kcal_mol", "pKi", "md_stable", "md_runtime_s"]
    for c in cols_needed:
        if c not in df.columns:
            df[c] = pd.NA

    df = df.dropna(subset=["dg_pred_kcal_mol", "pKi"]).copy()

    # Optional: only keep stable MD runs
    df = df[df["md_stable"] == True]

    # Per (param_set, protein) Spearman
    per_pp = []
    for (ps, protein), g in df.groupby(["param_set_id", "protein_id"]):
        if len(g) < 3:
            continue
        rho = g["dg_pred_kcal_mol"].corr(g["pKi"], method="spearman")
        per_pp.append({"param_set_id": ps, "protein_id": protein, "spearman_rho": rho, "n": len(g)})

    per_pp_df = pd.DataFrame(per_pp)
    analysis_dir = PROJECT_ROOT / "analysis"
    analysis_dir.mkdir(exist_ok=True)

    per_pp_path = analysis_dir / "per_protein_spearman.csv"
    per_pp_df.to_csv(per_pp_path, index=False)

    # Aggregate across proteins per param_set
    if not per_pp_df.empty:
        summary = (
            per_pp_df.groupby("param_set_id")
            .agg(mean_spearman=("spearman_rho", "mean"), median_spearman=("spearman_rho", "median"), proteins=("protein_id", "nunique"))
            .reset_index()
            .sort_values(["mean_spearman"], ascending=False)
        )
    else:
        summary = pd.DataFrame(columns=["param_set_id", "mean_spearman", "median_spearman", "proteins"])

    # Add rough runtime (sum of md_runtime_s) as a toy cost
    rt = df.groupby("param_set_id")["md_runtime_s"].sum(min_count=1).reset_index().rename(columns={"md_runtime_s": "total_md_runtime_s"})
    summary = summary.merge(rt, on="param_set_id", how="left")

    summary_path = analysis_dir / "summary_by_param_set.csv"
    summary.to_csv(summary_path, index=False)

    print("Wrote:")
    print(f" - {per_pp_path}")
    print(f" - {summary_path}")
    print()
    print(summary)


if __name__ == "__main__":
    main()
