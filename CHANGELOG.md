# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2026-03-16

### Added
- Grid blocks in `pipeline.toml`/`.yaml`: `[[grid]]` sections define parameter sweeps via Cartesian product. List-valued keys are expanded; scalar keys are fixed. Named grids can be referenced selectively from experiment blocks. Grids and experiments are crossed automatically when both are present.
- Grid sweep example in `examples/sweep-example/` with full documentation in `docs/getting-started.md`.

### Fixed
- `get_parent()` now accepts an optional `sp_key` parameter, fixing silent breakage when a `DependencySpec` uses a non-default key.
- `collect_params_with_parents` now raises `DependencyResolutionError` instead of a bare `LookupError` when a parent is missing, consistent with the rest of the library.

### Added
- `ActionSpec.dep_sp_key` property — returns `dependency.sp_key` if a dependency exists, otherwise `DEFAULT_PARENT_SP_KEY`. Centralises parent-key resolution across `collect`, `migrate`, and `row_utils`.
- `RESERVED_DOC_KEYS` is now a public `frozenset` exported from `grubicy`, so callers can filter job document keys without reimplementing the list.

## [1.2.0] - 2026-02-26
- Added pydantic as a dependency
- Added the module `grubicy.typed` which provides helpers to automatically map the statepoint to a defined pydantic model
- Added an example on how to use the new pydantic bindings
- Removed the need to specify `--project .` whenever running a command
- Polished some code

## [1.1.0] - 2026-02-19
- Add `grubicy submit` readiness filtering that uses row status (completed/submitted/waiting, eligible) plus parent completion before submitting.
- Refactor readiness with `RowStatus` and shared parent resolution (`get_parent`).
- Integration tests now build and use the row CLI via cargo; CI split into unit and integration jobs with cargo caching.
- Documentation and examples recommend `grubicy submit` as the default way to run ready jobs; describe readiness rules and default project resolution.

## [1.0.0]
- Initial release.
