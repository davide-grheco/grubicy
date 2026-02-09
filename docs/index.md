# grubicy

grubicy is a small helper library + CLI that layers lightweight dependency management on top of signac.

It is named after Vittore Grubicy de Dragon, an influential promoter of Italian Divisionism—a movement that “divided” light and color into strokes. grubicy does the same for workflows: it divides a signac project into stages, connects them with explicit parent -> child links, and keeps those links consistent even as your schema evolves.

With one TOML/YAML spec you can:

- describe multi-action pipelines in a single file,
- materialize signac jobs with parent pointers stored in state points,
- record full parent state points in docs for traceability (`deps_meta`),
- render row workflows, and
- migrate existing workspaces with cascading pointer updates without doing it by hand.

## Why use it

Signac projects are naturally flat, but real computational work is often staged:

- Prepare -> simulate -> analyze
- Preprocess -> train -> evaluate
- Extract -> transform -> aggregate

grubicy helps when you want those stages to be:

- cached and reusable (shared intermediates across experiments),
- explicitly wired (no hidden coupling via shared parameter keys),
- reviewable and reproducible (the pipeline is a spec file),
- maintainable over time (schema changes do not break downstream links).

What you get:

- Explicit dependencies: parent job ids live in the child state point, so “same params but different parents” never collide.
- One spec for everything: job creation, row workflow rendering, and parameter collection are driven by a single config file.
- Safe migrations: plan/apply state point migrations and automatically cascade dependency-pointer rewrites downstream, with progress logging.

When to use it:

- Use grubicy if you have multi-step experiments, pass results downstream between stages, or want row-ready workflows without writing manual include filters.
- If your project is truly single-stage, grubicy will feel like extra structure you do not need.
