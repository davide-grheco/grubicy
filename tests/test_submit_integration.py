import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


signac = pytest.importorskip("signac")


def _write_pipeline(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            [workspace]
            value_file = "signac_statepoint.json"

            [[actions]]
            name = "s1"
            sp_keys = ["p"]
            outputs = ["s1/out.txt"]

            [[actions]]
            name = "s2"
            sp_keys = ["q"]
            outputs = ["s2/out.txt"]
            deps = { action = "s1" }

            [[experiment]]
              [experiment.s1]
              p = 1
              [experiment.s2]
              q = 10

            [[experiment]]
              [experiment.s1]
              p = 2
              [experiment.s2]
              q = 20
            """
        ),
        encoding="utf-8",
    )


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("row") is None, reason="row CLI not available")
def test_submit_only_eligible(tmp_path, monkeypatch):
    pipeline = tmp_path / "pipeline.toml"
    _write_pipeline(pipeline)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    workflow_path = project_dir / "workflow.toml"

    # Materialize jobs and render workflow
    spec = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "prepare",
            str(pipeline),
            "--project",
            str(project_dir),
            "--output",
            str(workflow_path),
        ],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    if spec.returncode != 0:
        raise RuntimeError(f"prepare failed: {spec.stderr}")

    project = signac.Project(str(project_dir))

    # Mark one s1 job as completed by writing its declared output
    for job in project.find_jobs({"action": "s1"}):
        if job.sp["p"] == 1:
            out = Path(job.path) / "s1" / "out.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("done", encoding="utf-8")

    # Rescan row so eligibility reflects outputs
    scan = subprocess.run(
        ["row", "scan"], cwd=project_dir, capture_output=True, text=True
    )
    if scan.returncode != 0:
        raise RuntimeError(f"row scan failed: {scan.stderr}")

    # Build expected ready sets based on project state
    s1_pending = {
        job.id for job in project.find_jobs({"action": "s1"}) if job.sp["p"] == 2
    }
    s2_expected = set()
    for job in project.find_jobs({"action": "s2"}):
        parent_id = job.sp["parent_action"]
        parent_job = project.open_job(id=parent_id)
        if (Path(parent_job.path) / "s1" / "out.txt").exists():
            s2_expected.add(job.id)

    # Dry-run submit for s1: should list only the incomplete s1 job(s)
    res_s1 = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "submit",
            str(pipeline),
            "-p",
            str(project_dir),
            "--action",
            "s1",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert res_s1.returncode == 0, res_s1.stderr
    lines = [
        ln
        for ln in res_s1.stdout.splitlines()
        if ln and not ln.startswith("row submit")
    ]
    assert set(lines) == s1_pending

    # Dry-run submit for s2: should include only s2 jobs whose parents are completed
    res_s2 = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "submit",
            str(pipeline),
            "-p",
            str(project_dir),
            "--action",
            "s2",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert res_s2.returncode == 0, res_s2.stderr
    lines = [
        ln
        for ln in res_s2.stdout.splitlines()
        if ln and not ln.startswith("row submit")
    ]
    assert set(lines) == s2_expected

    # Dry-run submit without filtering action: should combine ready s1 and s2
    res_all = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "submit",
            str(pipeline),
            "-p",
            str(project_dir),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert res_all.returncode == 0, res_all.stderr
    lines_all = [
        ln
        for ln in res_all.stdout.splitlines()
        if ln and not ln.startswith("row submit")
    ]
    assert set(lines_all) == s1_pending | s2_expected


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("row") is None, reason="row CLI not available")
def test_submit_defaults_use_cwd_project(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    pipeline = project_dir / "pipeline.toml"
    _write_pipeline(pipeline)

    # prepare without --project (should use cwd) and with config in cwd
    spec = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "prepare",
            "pipeline.toml",
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if spec.returncode != 0:
        raise RuntimeError(f"prepare failed: {spec.stderr}")

    project = signac.Project(str(project_dir))

    # Mark one s1 job as completed
    for job in project.find_jobs({"action": "s1"}):
        if job.sp["p"] == 1:
            out = Path(job.path) / "s1" / "out.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("done", encoding="utf-8")

    # Rescan row
    scan = subprocess.run(
        ["row", "scan"], cwd=project_dir, capture_output=True, text=True
    )
    if scan.returncode != 0:
        raise RuntimeError(f"row scan failed: {scan.stderr}")

    s1_pending = {
        job.id for job in project.find_jobs({"action": "s1"}) if job.sp["p"] == 2
    }
    s2_expected = set()
    for job in project.find_jobs({"action": "s2"}):
        parent_id = job.sp["parent_action"]
        parent_job = project.open_job(id=parent_id)
        if (Path(parent_job.path) / "s1" / "out.txt").exists():
            s2_expected.add(job.id)

    res_all = subprocess.run(
        [
            "python",
            "-m",
            "grubicy.cli",
            "submit",
            "pipeline.toml",
            "--dry-run",
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    assert res_all.returncode == 0, res_all.stderr
    lines_all = [
        ln
        for ln in res_all.stdout.splitlines()
        if ln and not ln.startswith("row submit")
    ]
    assert set(lines_all) == s1_pending | s2_expected
