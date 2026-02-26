# Changelog

All notable changes to this project will be documented in this file.

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
