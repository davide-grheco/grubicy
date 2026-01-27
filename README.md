# GBSA Study Demo (signac + row)

This is a **toy project** that mimics the structure of an MD/GBSA benchmark study:
- Proteins: PDB files in `inputs/proteins/`
- Ligands: SMILES + (optional) experimental Ki/IC50 in `inputs/ligands.csv`
- Parameter sets: JSON files in `configs/param_sets/`
- signac jobs: created under `workspace/` via `scripts/populate_workspace.py`
- row workflow: actions defined in `workflow.toml` and implemented in `actions.py`

**No real calculations are run.** Actions only read the right inputs and write deterministic random outputs,
so you can test:
- selection and bookkeeping
- SLURM-style grouping via row (run locally with `--cluster=none`)
- retrieval and aggregation of results by `param_set_id`

## 1) Install

### Python deps
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### row CLI
Row is a Rust CLI. One convenient install method is `cargo binstall row`:
- Install Rust/Cargo: https://doc.rust-lang.org/cargo/getting-started/installation.html
- Install cargo-binstall, then:
```bash
cargo binstall row
```
(Alternative: `cargo install row`)

## 2) Initialize the project

```bash
# Initialize signac
signac init

# Populate workspace with jobs
python scripts/populate_workspace.py
```

## 3) Run the dummy workflow locally (no SLURM)

```bash
row show status
row submit --cluster=none --action ligand_param
row submit --cluster=none --action docking
row submit --cluster=none --action md
row submit --cluster=none --action gbsa
row submit --cluster=none --action metrics
```

## 4) Aggregate results by parameter set

```bash
python scripts/aggregate_results.py
```

Outputs:
- `analysis/summary_by_param_set.csv`
- `analysis/per_protein_spearman.csv`

## 5) "Add a new parameter later" (constant across existing runs)

This demo keeps job identity stable by storing only `param_set_id` in the state point.
To add a constant parameter across already-run jobs, write it into `job.doc`:

```bash
python scripts/migrations/add_constant_param_to_doc.py --key new_param --value 123
```

(If you truly need it in the **state point**, that changes job ids; avoid unless necessary.)
