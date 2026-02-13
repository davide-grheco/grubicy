# Migrations

This page shows how to migrate an existing signac workspace when an action's state
point schema changes.

In grubicy, downstream jobs store the upstream job id in their own state point (via
`deps.sp_key`, default `parent_action`). When you change an upstream action's state
point, job ids can change, so those downstream pointers must be rewritten.

grubicy migrations are two-phase:

- `migrate-plan`: compute old -> new ids/state points and detect collisions.
- `migrate-apply`: mutate state points (and copy workspaces if needed), then cascade
  pointer rewrites downstream, with progress logging for resume.

## Worked example: add a defaulted key to an upstream action

Scenario: you want to add a new key `b` to the `s1` action, defaulting to `0` for all
existing `s1` jobs.

### 1) Before: pipeline spec

Your `pipeline.toml` might look like:
```toml
[[actions]]
name = "s1"
sp_keys = ["p1"]

[[experiment]]
  [experiment.s1]
  p1 = 1
```

### 2) Create a plan

From the signac project directory:
```bash
grubicy migrate-plan pipeline.toml s1 --project . --setdefault b=0
```

This writes a plan under `.pipeline_migrations/` (for example
`.pipeline_migrations/plan_s1_YYYYmmddTHHMMSS.json`).

If your config is TOML, `migrate-plan` also updates `pipeline.toml` to include the
new key in:

- the action's `sp_keys`
- each experiment's `[experiment.s1]` block (only if it already exists) when the key
  is missing

If your config is not TOML, you must update it manually.

### 3) Inspect the plan (optional)

You can view the plan by running `migrate-apply` in `--dry-run` mode:
```bash
grubicy migrate-apply pipeline.toml s1 --project . --dry-run
```

`--dry-run` prints the plan JSON (it does not change the workspace).

To use a specific plan file (instead of the latest one), pass `--plan`:
```bash
grubicy migrate-apply pipeline.toml s1 --project . --plan .pipeline_migrations/plan_s1_YYYYmmddTHHMMSS.json --dry-run
```

### 4) Apply the migration

```bash
grubicy migrate-apply pipeline.toml s1 --project .
```

What happens during apply:

- `s1` jobs get updated state points (here: `b` is added if missing).
- If an `s1` job id changes, its workspace directory is copied to the new job id.
- All downstream actions are scanned in topological order; any parent pointer state
  point keys that reference an old id are rewritten to the new id.
- Progress is written under `.pipeline_migrations/run_s1_YYYYmmddTHHMMSS/progress.json`
  so you can resume after interruptions.

After applying, it is usually a good idea to regenerate your row workflow:
```bash
grubicy render-row pipeline.toml --output workflow.toml
```

## Collisions

With the currently supported CLI migration transform (`--setdefault`, which only adds
new keys and does not overwrite existing values), collisions are not expected: adding
a key preserves the existing distinctions between jobs.

grubicy still performs collision detection as a safety check, but if you are only
using `migrate-plan ... --setdefault ...`, you should treat collisions as an
unexpected sign that the workspace already contains inconsistent/duplicate state
points for that action.

## Resume and locking

`migrate-apply` is restartable by default. If interrupted, rerun the same command and
it will resume from the progress log. Use `--no-resume` to force a fresh run.

To prevent concurrent migrations, apply uses a lock file `.pipeline_lock` in the
project directory. If you get a lock error, ensure no other migration is running. If
the lock is stale (e.g. after a crash), remove `.pipeline_lock` and rerun.

## Tips

- Prefer migrating upstream actions first (roots), then downstream, to keep pointer
  rewrites simple.
- Run `grubicy status pipeline.toml --project .` after a migration to see which
  jobs are missing declared products.
- Keep `.pipeline_migrations/` in your project directory; it contains the plan and the
  apply progress logs used for audit and resume.
