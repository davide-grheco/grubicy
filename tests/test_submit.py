import os
import subprocess
import sys
from pathlib import Path

from grubicy.row_utils import (
    _list_directories_with_status,
    ready_directories,
    submit_directories,
)
from grubicy.spec import WorkflowSpec


def test_list_status_parses_output(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, cwd, capture_output, text, check):
        calls.append((cmd, cwd))
        return subprocess.CompletedProcess(cmd, 0, stdout="a\n\nb\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = _list_directories_with_status(tmp_path, "--completed", action="s2")

    assert result == {"a", "b"}
    assert calls[0][0] == [
        "row",
        "show",
        "directories",
        "--completed",
        "--short",
        "--action",
        "s2",
    ]
    assert calls[0][1] == str(tmp_path)


def test_submit_directories_builds_command(monkeypatch, tmp_path):
    seen = []

    def fake_run(cmd, cwd, capture_output, text, check):
        seen.append((cmd, cwd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    submit_directories(
        tmp_path,
        ["d1", "d2"],
        action="s2",
        limit=1,
        dry_run=True,
    )

    cmd, cwd = seen[0]
    assert cmd[:3] == ["row", "submit", "--yes"]
    assert "--dry-run" in cmd
    assert "--action" in cmd and "s2" in cmd
    assert "-n" in cmd and "1" in cmd
    assert cmd[-2:] == ["d1", "d2"]
    assert cwd == str(tmp_path)


def test_ready_directories(monkeypatch, tmp_path):
    # Fake row status sets
    def fake_status(project_path, status_flag, action):
        if status_flag == "--completed":
            return {"p1", "c1"}
        if status_flag == "--submitted":
            return {"sub"}
        if status_flag == "--waiting":
            return set()
        return set()

    monkeypatch.setattr(
        sys.modules["grubicy.row_utils"], "_list_directories_with_status", fake_status
    )

    spec = WorkflowSpec.from_mapping(
        {
            "actions": [
                {"name": "s1", "sp_keys": []},
                {"name": "s2", "sp_keys": [], "deps": {"action": "s1"}},
            ],
            "experiments": [],
        }
    )

    class Job:
        def __init__(self, id, sp):
            self.id = id
            self.sp = sp

    class FakeProject:
        path = tmp_path

        def find_jobs(self, query):
            if query["action"] == "s1":
                return [Job("p1", {"action": "s1"}), Job("p2", {"action": "s1"})]
            return [
                Job("c1", {"action": "s2", "parent_action": "p1"}),
                Job("c2", {"action": "s2", "parent_action": "p2"}),
            ]

        def open_job(self, id):
            raise NotImplementedError

    project = FakeProject()

    ready = ready_directories(spec, project)
    assert ready == ["p2"]
