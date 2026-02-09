"""Command-line interface for signac-deps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import signac
import tomli_w
import tomllib

from .collect import collect_params_with_parents
from .materialize import materialize
from .migrate import MigrationPlan, execute_migration, plan_migration
from .row_render import render_row_workflow
from .spec import load_spec


def _parse_key_values(items: list[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Invalid key=value pair: {item}")
        key, value = item.split("=", 1)
        result[key] = value
    return result


def cmd_validate(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    _ = spec.topological_actions()
    print(f"Validated config: {args.config}")


def _get_or_init_project(path: str | None = None) -> signac.Project:
    if path:
        try:
            return signac.Project(path)
        except LookupError:
            return signac.init_project(path=path)
    try:
        return signac.get_project()
    except LookupError:
        return signac.init_project()


def _update_config_for_defaults(
    config_path: str, action_name: str, defaults: Dict[str, str]
) -> None:
    path = Path(config_path)
    if path.suffix.lower() != ".toml":
        return
    data = path.read_text(encoding="utf-8")
    try:
        cfg = tomllib.loads(data)
    except Exception:
        return
    changed = False
    actions = cfg.get("actions") or []
    for entry in actions:
        if entry.get("name") != action_name:
            continue
        sp_keys = set(entry.get("sp_keys", []))
        before = set(sp_keys)
        sp_keys.update(defaults.keys())
        if sp_keys != before:
            entry["sp_keys"] = list(sp_keys)
            changed = True

    experiments = cfg.get("experiments") or cfg.get("experiment") or []
    for exp in experiments:
        if not isinstance(exp, dict):
            continue
        block = exp.get(action_name)
        if block is None:
            continue
        for k, v in defaults.items():
            if k not in block:
                block[k] = v
                changed = True

    if changed:
        path.write_text(tomli_w.dumps(cfg), encoding="utf-8")


def cmd_materialize(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    report = materialize(spec, project, spec.experiments, dry_run=args.dry_run)
    if getattr(args, "format", "json") == "json":
        print(json.dumps(report.__dict__, indent=2, default=str))
    else:
        counts = ",".join(f"{k}:{len(v)}" for k, v in report.per_action.items())
        print(f"materialize total={report.total} created={report.created} [{counts}]")


def cmd_render_row(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    out = render_row_workflow(spec, args.output)
    print(f"Wrote row workflow to {out}")


def cmd_migrate_plan(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    defaults = _parse_key_values(args.setdefault)

    def transform(sp: dict) -> dict:
        sp = dict(sp)
        for k, v in defaults.items():
            sp.setdefault(k, v)
        return sp

    plan = plan_migration(
        spec,
        project,
        args.action,
        transform,
        collision_strategy=args.collision_strategy,
    )
    _update_config_for_defaults(args.config, args.action, defaults)
    print(f"Wrote migration plan: {plan.plan_path}")


def cmd_migrate_execute(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    plan_path = _resolve_plan_path(project, args.plan)
    plan = MigrationPlan.from_path(plan_path)
    if getattr(args, "dry_run", False):
        print(json.dumps(plan.to_dict(), indent=2))
        return
    report = execute_migration(spec, project, plan, resume=not args.no_resume)
    if getattr(args, "format", "json") == "json":
        print(json.dumps(report.__dict__, indent=2, default=str))
    else:
        counts = ", ".join(f"{k}:{v}" for k, v in report.updated_actions.items())
        print(f"apply plan {plan_path} updated {{{counts}}}")


def cmd_status(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    summary = {}
    for action in spec.actions:
        jobs = list(project.find_jobs({"action": action.name}))
        missing_products = 0
        for job in jobs:
            for prod in action.outputs or []:
                if not Path(job.fn(prod)).exists():
                    missing_products += 1
                    break
        summary[action.name] = {
            "count": len(jobs),
            "missing_products": missing_products,
        }
    if getattr(args, "missing_only", False):
        summary = {k: v for k, v in summary.items() if v["missing_products"]}
    if getattr(args, "format", "json") == "json":
        print(json.dumps(summary, indent=2))
    else:
        for name, meta in summary.items():
            print(f"{name}: count={meta['count']} missing={meta['missing_products']}")


def cmd_collect_params(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    rows = collect_params_with_parents(
        spec,
        project,
        args.action,
        include_doc=args.include_doc,
        missing_ok=args.missing_ok,
    )
    if args.format == "json":
        payload = [row.data for row in rows]
        text = json.dumps(payload, indent=2)
    else:
        # csv
        import csv
        from io import StringIO

        payload = [row.data for row in rows]
        # Union of keys in order of appearance
        keys: list[str] = []
        for row in payload:
            for k in row.keys():
                if k not in keys:
                    keys.append(k)
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=keys)
        writer.writeheader()
        writer.writerows(payload)
        text = buffer.getvalue()
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)


def cmd_prepare(args: argparse.Namespace) -> None:
    spec = load_spec(args.config)
    project = _get_or_init_project(args.project)
    materialize(spec, project, spec.experiments, dry_run=False)
    out = None
    if not getattr(args, "no_render", False):
        out = render_row_workflow(spec, args.output)
    msg = f"Prepared project at {project.path}"
    if out:
        msg += f"; workflow={out}"
    print(msg)


def _resolve_plan_path(project: signac.Project, provided: str | None) -> Path:
    if provided:
        return Path(provided)
    plans = sorted(Path(project.path).glob(".pipeline_migrations/plan_*.json"))
    if not plans:
        raise SystemExit("No migration plans found; specify --plan")
    return plans[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="signac-deps", description="signac-deps CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="Validate a config")
    p_val.add_argument("config")
    p_val.set_defaults(func=cmd_validate)

    p_mat = sub.add_parser("materialize", help="Materialize jobs")
    p_mat.add_argument("config")
    p_mat.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD)"
    )
    p_mat.add_argument("--dry-run", action="store_true")
    p_mat.add_argument("-f", "--format", choices=["json", "table"], default="table")
    p_mat.set_defaults(func=cmd_materialize)

    p_row = sub.add_parser("render-row", help="Render row workflow")
    p_row.add_argument("config")
    p_row.add_argument("-o", "--output", default="workflow.toml")
    p_row.set_defaults(func=cmd_render_row)

    p_plan = sub.add_parser(
        "migrate-plan", help="Create a migration plan with setdefault"
    )
    p_plan.add_argument("config")
    p_plan.add_argument("action")
    p_plan.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD or init)"
    )
    p_plan.add_argument(
        "--setdefault", nargs="*", default=[], help="key=value defaults to add"
    )
    p_plan.add_argument(
        "--collision-strategy",
        choices=["abort", "keep-first"],
        default="abort",
    )
    p_plan.set_defaults(func=cmd_migrate_plan)

    p_exec = sub.add_parser("migrate-apply", help="Execute a migration plan")
    p_exec.add_argument("config")
    p_exec.add_argument("action")
    p_exec.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD or init)"
    )
    p_exec.add_argument("--plan", help="Path to plan file (defaults to latest)")
    p_exec.add_argument("--dry-run", action="store_true")
    p_exec.add_argument("--no-resume", action="store_true")
    p_exec.add_argument("-f", "--format", choices=["json", "table"], default="table")
    p_exec.set_defaults(func=cmd_migrate_execute)

    p_status = sub.add_parser("status", help="Summarize jobs per action")
    p_status.add_argument("config")
    p_status.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD or init)"
    )
    p_status.add_argument("-f", "--format", choices=["json", "table"], default="table")
    p_status.add_argument("--missing-only", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_collect = sub.add_parser(
        "collect-params", help="Collect params (and optional docs) across parent chain"
    )
    p_collect.add_argument("config")
    p_collect.add_argument("action", help="Target action to collect")
    p_collect.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD or init)"
    )
    p_collect.add_argument(
        "-f", "--format", choices=["json", "csv"], default="json", help="Output format"
    )
    p_collect.add_argument(
        "--include-doc",
        action="store_true",
        help="Include document fields (excluding reserved)",
    )
    p_collect.add_argument(
        "--missing-ok",
        action="store_true",
        help="Skip rows whose parents are missing (default: error)",
    )
    p_collect.add_argument(
        "-o", "--output", help="Write output to file instead of stdout"
    )
    p_collect.set_defaults(func=cmd_collect_params)

    p_prepare = sub.add_parser("prepare", help="Validate, materialize, render row")
    p_prepare.add_argument("config")
    p_prepare.add_argument(
        "-p", "--project", help="Path to signac project (defaults to CWD)"
    )
    p_prepare.add_argument("-o", "--output", default="workflow.toml")
    p_prepare.add_argument("--no-render", action="store_true")
    p_prepare.set_defaults(func=cmd_prepare)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
