# Changelog

All notable changes to the Delimit GitHub Action will be documented in this file.

## [1.7.0] - 2026-03-26

### Features
- "Keep Building." displayed on governance pass (0 breaking changes)
- Auto-detect OpenAPI spec when no path provided (scans common locations)
- 27 change types (expanded from 23): 17 breaking, 10 non-breaking
- Severity badges in PR comments (Critical, High, Medium)
- Claude Code Action workflow included in examples
- E2E smoke test workflow for action validation

## [1.3.0] - 2026-03-15

### Testing
- Added 87 MCP bridge smoke tests covering all tool endpoints
- Added 151 core engine tests for ci_formatter, policy_engine, and semver_classifier
- 488 total tests passing across gateway and action (up from 299)
- Test coverage improved from 57% to 65%

### Features
- Enhanced PR comments with severity badges and migration guides
- Added sensor tool for outreach monitoring (delimit_sensor_github_issue)

### Fixes
- Fixed async deprecation warnings in bridge layer (run_async helper)
- Fixed $ref pointer resolution before schema comparison
- Fixed spec deletion crash with guard clause
- Fixed test_sensor_github_issue collection error

### Security
- Internal bridge token moved from hardcoded value to environment variable

## [1.2.0] - 2026-03-10

### Features
- Semver classification with deterministic MAJOR/MINOR/PATCH/NONE
- Explainer templates for PR comments (7 templates)
- Policy presets: strict, default, relaxed
- Enforce mode: fail CI on breaking changes
- PR comment with breaking change tables and migration guides

### Testing
- 49-test suite for action core
- 250 gateway tests passing

## [1.1.0] - 2026-03-08

### Features
- Policy engine with custom YAML rules
- Advisory and enforce modes
- GitHub annotations for violations

## [1.0.0] - 2026-03-06

### Features
- Initial release
- OpenAPI diff engine with 23 change types
- Breaking change detection (10 types)
- PR comment integration
