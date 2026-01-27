"""Add a constant parameter to job documents (non-breaking migration).

This is the recommended way to 'add a parameter later' when:
- it was implicitly constant in previous runs, OR
- you want to annotate existing results without changing job identity.

Usage:
  python scripts/migrations/add_constant_param_to_doc.py --key foo --value 123
"""

from __future__ import annotations

import argparse
import json
import signac


def parse_value(s: str):
    # Try JSON first so you can pass numbers/bools/objects.
    try:
        return json.loads(s)
    except Exception:
        return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--value", required=True)
    ap.add_argument("--only-if-missing", action="store_true", default=True)
    args = ap.parse_args()

    value = parse_value(args.value)
    project = signac.get_project()

    n = 0
    for job in project:
        if args.only_if_missing and args.key in job.doc:
            continue
        job.doc[args.key] = value
        n += 1

    print(f"Updated {n} jobs: set job.doc['{args.key}'] = {value!r}")


if __name__ == "__main__":
    main()
