# Changelog

All notable changes to the Delimit GitHub Action will be documented in this file.

## [1.10.0] - 2026-04-24

### Features
- **"Learn more" link on breaking-change PR comments (LED-1086)** — when a breaking change is detected, the PR comment now includes a single link to `https://delimit.ai/api-breaking-changes` with public GitHub metadata as URL parameters (repo, PR number, top change type). Consent-based; the Action makes no outbound calls. Link is suppressed when there are no breaking changes so clean PRs stay quiet. Both OpenAPI and JSON Schema renderers.

### Infrastructure
- **Signed releases via Sigstore + SLSA (LED-1088)** — new `.github/workflows/release.yml` produces four artifacts per tag push: source tarball, SHA256 checksum, **Sigstore bundle** (keyless OIDC signing, Rekor-logged), and a **CycloneDX SBOM**. Plus a separate SLSA build-provenance attestation via `actions/attest-build-provenance@v2`, verifiable with `gh attestation verify <tag>.tar.gz --owner delimit-ai`. This release (v1.10.0) is the first signed release; the Sigstore bundle and SBOM are attached to the GitHub release.

### Docs
- **SECURITY.md threat model (LED-1089)** — expanded from a thin policy into a full threat model with install-time vs runtime surfaces documented separately. Includes pinning guidance, Cosign verification command, explicit file-read/write enumeration, outbound network claim (`api.github.com` only, no `delimit.ai` calls), `GITHUB_TOKEN` minimum scopes, and a clear out-of-scope section.

### Fixed
- **Learn more URL target** — initial LED-1086 pointed at `/action-help` (unbuilt route). Corrected to `/api-breaking-changes` (existing SEO-optimized page) so clicks don't 404. URL parameters preserved.

### Why this release
First release in the v2 distribution plan arc (post-2026-04-24 adversarial rebuttal, 92/100 confidence). The rebuttal required Sigstore-verifiable releases before any public CLI or MCP launch. This is that foundation — the installer artifact developers can verify without trusting a pinky promise.

### Tests
- Existing 195 tests pass. No behavior changes on the enforcement path.

## [1.9.1] - 2026-04-09

### Fixed
- **github-script comment-post 403 unhandled throw (LED-807)** — when consumer workflows did not grant `permissions: pull-requests: write`, the JSON Schema and OpenAPI comment-post steps would unhandled-throw on `Resource not accessible by integration` and hang the action run. Both comment paths are now wrapped in `try/catch` with explicit 403 handling that emits `core.warning` (run still succeeds) and never rethrows. Non-403 errors still rethrow. The dedicated "Enforce breaking change policy" step is unchanged. Unblocks `agents-oss/agentspec#39` outreach conversion — external maintainer @skokaina hit this live 2026-04-09.

### Tests
- New: `tests/test_action_yml_comment_403.py` — 9 tests covering the 403 branch, the non-403 rethrow branch, and that the comment step never gates the run.
- Total: 195 passing.

## [1.9.0] - 2026-04-07

### Features
- **JSON Schema support** (LED-713) — first-class governance for bare JSON Schema files (Draft 4+, single-file, internal `$ref` resolution). Complements OpenAPI without changing the existing path. Routes via `core/spec_detector.detect_spec_type()`.
- **Generator drift detection** — new `generator_command` + `generator_artifact` inputs. When set, the action runs the regen command in a sandbox and diffs the regenerated output against the committed artifact. Catches the case where source-of-truth (Zod, protobuf, OpenAPI generator, etc.) has changed but the committed generated file is stale. Workspace is cleanly restored after the check.
- **`fail_on_breaking` input** — boolean alias for `mode=enforce`. When `true`, fails CI on breaking changes regardless of `mode`. Defaults to `false`.
- **PR comment renderer** updated with a JSON Schema branch that shows drift report + classification table.

### v1 JSON Schema change types
Property add/remove, required add/remove, type widen/narrow, enum value add/remove, `const` change, `additionalProperties` flip, `pattern` tighten/loosen, `minLength`/`maxLength`, `minimum`/`maximum`, `items` type. Composition keywords (`anyOf`/`oneOf`/`allOf`), discriminators, external `$ref`, and `if/then/else` deferred past v1.

### Tests
- 41 new unit tests in `tests/test_json_schema_diff.py` covering every v1 change type, $ref resolution at root and nested paths, dispatcher routing, and the agents-oss/agentspec rename as a real-world fixture
- 47 existing OpenAPI tests still passing (no regressions)

### Why
Validating delimit-action against agents-oss/agentspec#21 (issue inviting integration) revealed that the diff engine returned `0 changes` on bare JSON Schema files. The maintainer had explicitly invited a PR. This release closes the gap before that PR opens.

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
