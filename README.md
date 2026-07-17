# Delimit — the merge gate for AI-written code

**Catch breaking API changes on every PR — with a signed, replayable attestation any reviewer can verify.**

Delimit runs on every pull request and diffs your OpenAPI / JSON Schema spec against the base branch. It posts a review comment that says what broke (breaking-change classification), how big the change is (semver bump), and how to fix it (migration guide) — plus a zero-config secret scan over the changed files. It then signs the result via Sigstore keyless signing (recorded in the public Rekor transparency log), so anyone can verify the outcome without trusting the runner. No API keys, no external services.

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-Delimit-blue)](https://github.com/marketplace/actions/delimit-merge-gate-for-ai-written-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![API Governance](https://delimit-ai.github.io/badge/pass.svg)](https://github.com/marketplace/actions/delimit-merge-gate-for-ai-written-code)
[![Worked examples](https://img.shields.io/badge/worked%20examples-delimit.ai%2Freports-blue)](https://delimit.ai/reports)

## Worked examples

Real, reproducible merge-gate runs against public API specs:

- **[OpenAI OpenAPI: a year of AI frontier evolution under a cross-vendor merge gate](https://delimit.ai/reports/openai-openapi-attestation)** — OpenAI (openai/openai-openapi)
- **[Stripe v1 OpenAPI: 57 days under a merge gate](https://delimit.ai/reports/stripe-openapi-attestation)** — Stripe (stripe/openapi)
- **[Anthropic API: 76 days under a cross-vendor merge gate](https://delimit.ai/reports/anthropic-api-attestation)** — Anthropic (anthropics/anthropic-sdk-python)
- **[Twilio v2010 OpenAPI: 55 days under a merge gate](https://delimit.ai/reports/twilio-api-attestation)** — Twilio (twilio/twilio-oai)
- **[Docusign eSignature v2.1 OpenAPI: 46 days under a merge gate](https://delimit.ai/reports/docusign-esign-attestation)** — Docusign (docusign/OpenAPI-Specifications)
- **[Supabase Auth OpenAPI: 57 days under a merge gate](https://delimit.ai/reports/supabase-auth-openapi-attestation)** — Supabase Auth (supabase/auth)
- **[cal.com v2 OpenAPI: 60 days under a merge gate](https://delimit.ai/reports/cal-com-v2-attestation)** — cal.com (calcom/cal.com)
- **[EU TED v3 procurement API: $ref'd component-schema drift under a merge gate](https://delimit.ai/reports/eu-ted-v3-attestation)** — European Commission (TED v3 Public API)
- **[Cross-agent handoff: one artifact, four CLIs](https://delimit.ai/reports/cross-agent-handoff)** — Cross-CLI session handoff (worked example)
- **[delimit-mcp-server (self-attestation): same merge gate, third artifact class](https://delimit.ai/reports/delimit-mcp-server-tdqs)** — delimit-mcp-server (self-attestation)

See the full index at [delimit.ai/reports](https://delimit.ai/reports). For the schema and signing methodology behind every report, see [delimit.ai/methodology/mcp-attestation](https://delimit.ai/methodology/mcp-attestation).

## What it looks like

<p align="center">
  <img src="docs/pr-comment.png" alt="Delimit PR comment showing breaking changes" width="700">
</p>

---

## Features

- **Zero-config secret scan (PR safety gate)** — on every pull request, deterministically scans the files changed against the base branch for leaked-secret patterns (private keys, AWS access keys, GitHub tokens, Stripe live keys, Slack tokens, Google API keys, GitLab tokens). No spec, no config required. Files over 1 MB are skipped. Surfaces a job-summary report and `secrets_detected` / `secrets_count` outputs; fails CI on a hit in `enforce` mode (advisory otherwise)
- **Breaking change detection** — catches 28 types of changes (17 breaking, 11 non-breaking) across endpoints, parameters, response schemas, types, enums, security, and constraints
- **Semver classification** — deterministic `major` / `minor` / `patch` / `none` bump recommendation with computed next version
- **Migration guides** — auto-generated step-by-step migration instructions for every breaking change
- **PR comments** — rich Markdown summary posted directly on your pull request, updated on each push
- **Signed, replayable attestation per PR (v1.11.0+)** — every run produces a Sigstore keyless-signed claim, recorded in the public Rekor transparency log, with a verifiable `delimit.ai/att/<id>` permalink in the PR comment. Any reviewer can verify without trusting the runner. Add `id-token: write` to your workflow permissions; the rest is automatic.
- **Advisory and enforce modes** — start with non-blocking warnings, promote to CI-gating when ready
- **Custom policies** — define your own governance rules in `.delimit/policies.yml` with path patterns, severity levels, and custom messages
- **7 explainer templates** — developer, team lead, product, migration, changelog, PR comment, and Slack formats

---

## Replay any decision at delimit.ai/att/<id>

Every signed run produces a bundle a third party can verify without trusting the runner. Click the URL printed in the PR comment and you'll land on a page like [delimit.ai/att/att_f86e1f51110e8ed6](https://delimit.ai/att/att_f86e1f51110e8ed6) — the panel that adjudicated, the per-model verdicts, the dissents preserved as evidence, and a copy-paste HMAC-SHA256 verifier so reviewers, auditors, and underwriters can check the signature locally.

For multi-agent teams running Claude, Codex, Gemini, and Grok in parallel, the replay URL is the proof artifact: cross-vendor adjudication is something single-vendor scanners can't ship by construction.

> Cross-vendor adjudication is the architectural property single-vendor scanners can't replicate. Independent panel signs, dissents survive, signature verifies locally.

---

## Quick Start

Add this file to `.github/workflows/api-check.yml`:

```yaml
name: API Contract Check
on: pull_request

jobs:
  delimit:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      id-token: write          # optional: enables the signed, replayable attestation
    steps:
      - uses: actions/checkout@v4
      - uses: delimit-ai/delimit-action@v1
        with:
          spec: api/openapi.yaml
```

That is it. Delimit auto-fetches the base branch version of your spec and diffs it against the PR changes. Runs in **advisory mode** by default — posts a PR comment but never fails your build.

`id-token: write` enables Sigstore keyless signing of the result. Every PR comment gets a verifiable `delimit.ai/att/<id>` permalink that any reviewer can inspect. If you don't grant this permission, the action gracefully no-ops the signing step and the comment falls back to the unsigned shape.

### What the PR comment looks like

When Delimit detects breaking changes, it posts a comment like this:

> **Delimit API Governance** | Breaking Changes Detected
>
> | Change | Path | Severity |
> |--------|------|----------|
> | endpoint_removed | `DELETE /pets/{petId}` | error |
> | type_changed | `/pets:GET:200[].id` (string → integer) | warning |
> | enum_value_removed | `/pets:GET:200[].status` | warning |
>
> **Semver**: MAJOR (1.0.0 → 2.0.0)
>
> <details><summary>Migration Guide (3 steps)</summary>
>
> **Step 1**: `DELETE /pets/{petId}` was removed. Update clients to use an alternative endpoint or remove calls to this path.
>
> **Step 2**: `id` changed from `string` to `integer`. Update serialization logic, type assertions, and database column types.
>
> **Step 3**: `status` enum value `"pending"` was removed. Update clients to stop sending this value.
>
> </details>

See the [live demo](https://github.com/delimit-ai/delimit-action-demo/pull/2) — a Users API migration with 23 breaking changes detected across 28 change types, severity badges, and a migration guide.

### Advanced: explicit base and head specs

If you need to compare specific files (e.g., pre-checked-out base branch), use `old_spec` and `new_spec` instead:

```yaml
      - uses: delimit-ai/delimit-action@v1
        with:
          old_spec: base/api/openapi.yaml
          new_spec: api/openapi.yaml
```

---

## Full Usage

```yaml
name: API Governance
on: pull_request

jobs:
  api-check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - name: Checkout base spec
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: base

      - uses: delimit-ai/delimit-action@v1
        id: delimit
        with:
          old_spec: base/api/openapi.yaml
          new_spec: api/openapi.yaml
          mode: enforce
          policy_file: .delimit/policies.yml
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - name: Use outputs
        if: always()
        run: |
          echo "Breaking changes: ${{ steps.delimit.outputs.breaking_changes_detected }}"
          echo "Violations: ${{ steps.delimit.outputs.violations_count }}"
          echo "Semver bump: ${{ steps.delimit.outputs.semver_bump }}"
          echo "Next version: ${{ steps.delimit.outputs.next_version }}"
```

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `spec` | No | `''` | Path to the changed OpenAPI or JSON Schema spec. On pull requests, Delimit auto-fetches the base branch version for comparison. |
| `old_spec` | No | `''` | Path to the old/base API specification file. |
| `new_spec` | No | `''` | Path to the new/changed API specification file. |
| `mode` | No | `advisory` | `advisory` (comments only) or `enforce` (fails CI on breaking changes). |
| `fail_on_breaking` | No | `false` | Boolean alias for `mode: enforce`. When `true`, fails CI on breaking changes regardless of `mode`. |
| `github_token` | No | `${{ github.token }}` | GitHub token used to post PR comments. |
| `policy_file` | No | `''` | Path to a custom policy file (e.g., `.delimit/policies.yml`). |
| `webhook_url` | No | `''` | Slack or Discord webhook URL. Delimit posts a notification when breaking changes are detected. Auto-detects the platform from the URL. |
| `generator_command` | No | `''` | Optional shell command that regenerates a generated artifact (e.g. `pnpm run schema:export`). When set, Delimit runs this command in a sandbox and diffs the regenerated output against the committed artifact to detect drift between source-of-truth and committed file. Pair with `generator_artifact`. See [Generator drift detection](#generator-drift-detection). |
| `generator_artifact` | No | `''` | Path to the generated artifact that `generator_command` produces (e.g. `schemas/v1/agent.schema.json`). Required when `generator_command` is set. |

> **Note**: Provide either `spec` for pull request workflows, or both `old_spec` and `new_spec` for explicit comparisons. If neither form is provided, the action exits with an error.

---

## Generator drift detection

Many repos commit a JSON Schema (or similar artifact) that is generated from a source-of-truth file — for example a Zod schema in TypeScript compiled to JSON Schema via `zodToJsonSchema`, or a Protobuf file compiled to OpenAPI. A common class of bug is that someone updates the source and forgets to regenerate the committed artifact, so the two drift apart silently.

Delimit can catch this on every PR by running the generator in a sandbox and diffing its output against the committed file.

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    spec: schemas/v1/agent.schema.json
    generator_command: pnpm run schema:export
    generator_artifact: schemas/v1/agent.schema.json
```

On every PR that touches the schema:

1. Delimit runs `generator_command` in a sandboxed copy of the working tree.
2. It reads the regenerated artifact and diffs it against the committed file.
3. Any drift is reported in the PR comment, classified using the same JSON Schema semantics as normal schema changes (property add/remove, required, type widen/narrow, enum, `const`, `additionalProperties`, pattern, length and numeric bounds).
4. The committed file is restored before the workflow exits — the working tree is never modified.

If the regenerated output matches the committed artifact exactly, no drift is reported and the check passes silently. If the generator fails (non-zero exit or missing output file), Delimit reports the failure as an advisory warning and continues with the normal schema diff.

This is separate from the base-branch schema diff. Both run on the same PR and are reported in the same comment:

- **Schema classification** — committed JSON Schema vs base branch (what changed in this PR)
- **Generator drift** — regenerated artifact vs committed file in this PR (is the committed file stale)

You can use either independently, or both together. `generator_command` is opt-in — leave it empty to skip the drift check entirely.

### Supported generators

Anything that produces a JSON Schema or OpenAPI file at a known path and exits with code `0`. Common examples:

```yaml
# Zod → JSON Schema via zodToJsonSchema
generator_command: pnpm run schema:export
generator_artifact: schemas/v1/agent.schema.json

# Protobuf → OpenAPI via buf or protoc-gen-openapi
generator_command: buf generate
generator_artifact: gen/openapi/api.yaml

# TypeBox → JSON Schema
generator_command: npm run build:schema
generator_artifact: dist/schema.json
```

The action needs whatever toolchain the generator depends on to already be installed in the workflow — add `actions/setup-node`, `pnpm/action-setup`, or equivalent steps before the Delimit step.

---

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `breaking_changes_detected` | `string` | `"true"` if any breaking change was found, `"false"` otherwise. |
| `violations_count` | `string` | Number of policy violations (errors + warnings). |
| `semver_bump` | `string` | Recommended version bump: `major`, `minor`, `patch`, or `none`. |
| `next_version` | `string` | Computed next version string (e.g., `2.0.0`). |
| `report` | `string` | Full JSON report of all detected changes, violations, and semver data. |
| `secrets_detected` | `string` | `"true"` if a leaked-secret pattern was found in any changed file, `"false"` otherwise. |
| `secrets_count` | `string` | Number of changed files containing a leaked-secret pattern. |

### Using outputs in subsequent steps

```yaml
- uses: delimit-ai/delimit-action@v1
  id: delimit
  with:
    old_spec: base/api/openapi.yaml
    new_spec: api/openapi.yaml

- name: Block release on breaking changes
  if: steps.delimit.outputs.breaking_changes_detected == 'true'
  run: |
    echo "Breaking changes detected — semver bump: ${{ steps.delimit.outputs.semver_bump }}"
    echo "Next version should be: ${{ steps.delimit.outputs.next_version }}"
    exit 1

- name: Auto-tag on minor bump
  if: steps.delimit.outputs.semver_bump == 'minor'
  run: |
    git tag "v${{ steps.delimit.outputs.next_version }}"
```

---

## Custom Policies

Create `.delimit/policies.yml` in your repository root to define governance rules beyond the defaults.

```yaml
# .delimit/policies.yml

# Set to true to replace all default rules with only your custom rules.
# Default: false (custom rules merge with defaults).
override_defaults: false

rules:
  # Forbid removing endpoints without deprecation
  - id: no_endpoint_removal
    name: Forbid Endpoint Removal
    change_types:
      - endpoint_removed
    severity: error      # error | warning | info
    action: forbid       # forbid | allow | warn
    message: "Endpoint {path} cannot be removed. Use deprecation headers instead."

  # Protect V1 API — no breaking changes allowed
  - id: protect_v1_api
    name: Protect V1 API
    description: V1 endpoints are frozen
    change_types:
      - endpoint_removed
      - method_removed
      - field_removed
    severity: error
    action: forbid
    conditions:
      path_pattern: "^/v1/.*"
    message: "V1 API is frozen. Changes must be made in V2."

  # Warn on type changes in 2xx responses
  - id: warn_response_type_change
    name: Warn Response Type Changes
    change_types:
      - type_changed
    severity: warning
    action: warn
    conditions:
      path_pattern: ".*:2\\d\\d.*"
    message: "Type changed at {path} — verify client compatibility."

  # Allow adding enum values (informational)
  - id: allow_enum_expansion
    name: Allow Enum Expansion
    change_types:
      - enum_value_added
    severity: info
    action: allow
    message: "Enum value added (non-breaking)."
```

### Available change types for rules

| Change type | Breaking | Description |
|-------------|----------|-------------|
| `endpoint_removed` | Yes | An API endpoint path was removed |
| `method_removed` | Yes | An HTTP method was removed from an endpoint |
| `required_param_added` | Yes | A new required parameter was added |
| `param_removed` | Yes | A parameter was removed |
| `response_removed` | Yes | A response status code was removed |
| `required_field_added` | Yes | A new required field was added to a request body |
| `field_removed` | Yes | A field was removed from a response |
| `type_changed` | Yes | A field's type was changed (e.g., string to integer) |
| `format_changed` | Yes | A field's format was changed (e.g., date to date-time) |
| `enum_value_removed` | Yes | An allowed enum value was removed |
| `endpoint_added` | No | A new endpoint was added |
| `method_added` | No | A new HTTP method was added to an endpoint |
| `optional_param_added` | No | A new optional parameter was added |
| `response_added` | No | A new response status code was added |
| `optional_field_added` | No | A new optional field was added |
| `enum_value_added` | No | A new enum value was added |
| `field_requirement_relaxed` | No | A field's `$ref`'d component schema relaxed a requirement (e.g. a required field became optional) |
| `description_changed` | No | A description was modified |

### Default rules

Delimit ships with 6 built-in rules that are always active unless you set `override_defaults: true`:

1. **Forbid Endpoint Removal** — endpoints cannot be removed (error)
2. **Forbid Method Removal** — HTTP methods cannot be removed (error)
3. **Forbid Required Parameter Addition** — new required params break clients (error)
4. **Forbid Response Field Removal** — removing fields from 2xx responses (error)
5. **Warn on Type Changes** — type changes flagged as warnings
6. **Allow Enum Expansion** — adding enum values is always safe (info)

---

## Slack / Discord Notifications

Get notified in Slack or Discord when breaking API changes are detected. Add a `webhook_url` input pointing to your channel's incoming webhook:

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    spec: api/openapi.yaml
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

The notification fires only when breaking changes are found. If the webhook URL is not set, this step is silently skipped.

### Supported platforms

| Platform | URL pattern | Payload format |
|----------|------------|----------------|
| **Slack** | `hooks.slack.com` | Block Kit with mrkdwn |
| **Discord** | `discord.com/api/webhooks` | Rich embed with color and fields |
| **Generic** | Anything else | Plain JSON event payload |

Delimit auto-detects the platform from the URL and formats the message accordingly. Webhook failures are logged as warnings but never fail your CI run.

### Discord example

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    spec: api/openapi.yaml
    webhook_url: ${{ secrets.DISCORD_WEBHOOK }}
```

### Generic webhook

Any URL that is not Slack or Discord receives a JSON payload:

```json
{
  "event": "breaking_changes_detected",
  "repo": "org/repo",
  "pr_number": 123,
  "pr_title": "Update user endpoints",
  "breaking_changes": 3,
  "additive_changes": 1,
  "semver": "MAJOR",
  "pr_url": "https://github.com/org/repo/pull/123"
}
```

---

## Advisory vs Enforce Mode

| Behavior | `advisory` (default) | `enforce` |
|----------|---------------------|-----------|
| PR comment | Yes | Yes |
| GitHub annotations | Yes | Yes |
| Fails CI on breaking changes | **No** | **Yes** |
| Exit code on violations | `0` | `1` |

**Start with advisory mode.** It gives your team visibility into API changes without blocking merges. Once your team is comfortable, switch to `enforce` to gate deployments.

```yaml
# Advisory — non-blocking (default)
- uses: delimit-ai/delimit-action@v1
  with:
    old_spec: base/api/openapi.yaml
    new_spec: api/openapi.yaml
    mode: advisory

# Enforce — blocks merge on breaking changes
- uses: delimit-ai/delimit-action@v1
  with:
    old_spec: base/api/openapi.yaml
    new_spec: api/openapi.yaml
    mode: enforce
```

---

## Examples

### Advisory mode (recommended starting point)

```yaml
name: API Check
on: pull_request

jobs:
  api-check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: base
      - uses: delimit-ai/delimit-action@v1
        with:
          old_spec: base/api/openapi.yaml
          new_spec: api/openapi.yaml
```

### Enforce mode

```yaml
name: API Governance
on: pull_request

jobs:
  api-check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: base
      - uses: delimit-ai/delimit-action@v1
        with:
          old_spec: base/api/openapi.yaml
          new_spec: api/openapi.yaml
          mode: enforce
```

### Custom policy file

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    old_spec: base/api/openapi.yaml
    new_spec: api/openapi.yaml
    mode: enforce
    policy_file: .delimit/policies.yml
```

### Using outputs to control downstream jobs

```yaml
jobs:
  api-check:
    runs-on: ubuntu-latest
    outputs:
      breaking: ${{ steps.delimit.outputs.breaking_changes_detected }}
      bump: ${{ steps.delimit.outputs.semver_bump }}
      next_version: ${{ steps.delimit.outputs.next_version }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: base
      - uses: delimit-ai/delimit-action@v1
        id: delimit
        with:
          old_spec: base/api/openapi.yaml
          new_spec: api/openapi.yaml

  deploy:
    needs: api-check
    if: needs.api-check.outputs.breaking != 'true'
    runs-on: ubuntu-latest
    steps:
      - run: echo "Safe to deploy — next version ${{ needs.api-check.outputs.next_version }}"
```

---

## Supported Formats

- OpenAPI 3.0 and 3.1
- Swagger 2.0
- YAML and JSON spec files

---

## What the PR Comment Looks Like

When Delimit detects changes, it posts (or updates) a comment on your pull request:

```
## Delimit: Breaking Changes `MAJOR`

| Metric | Value |
|--------|-------|
| Semver bump | `major` |
| Next version | `2.0.0` |
| Total changes | 5 |
| Breaking | 2 |
| Violations | 2 |

### Violations

| Severity | Rule | Description | Location |
|----------|------|-------------|----------|
| Error | Forbid Endpoint Removal | Endpoint /users/{id} cannot be removed | `/users/{id}` |
| Warning | Warn on Type Changes | Type changed from string to integer | `/users:200.age` |

<details>
<summary>Migration guide</summary>
...step-by-step instructions for each breaking change...
</details>
```

The comment is automatically updated on each push to the PR branch. No duplicate comments.

---

## FAQ / Troubleshooting

### Delimit skipped validation and did nothing

Both `old_spec` and `new_spec` must be provided. If either is empty, Delimit exits cleanly with no output. Make sure both paths point to valid spec files.

### How do I get the base branch spec?

Use a second `actions/checkout` step to check out the base branch into a subdirectory:

```yaml
- uses: actions/checkout@v4
  with:
    ref: ${{ github.event.pull_request.base.sha }}
    path: base
```

Then reference `base/path/to/openapi.yaml` as `old_spec`.

### My spec file is not found

Verify the path relative to the repository root. Common locations:
- `api/openapi.yaml`
- `docs/openapi.yaml`
- `openapi.yaml`
- `swagger.json`

### The action posts duplicate PR comments

Delimit searches for an existing comment containing "Delimit" from a bot user and updates it in place. If you see duplicates, ensure `github_token` has `pull-requests: write` permission.

### The action ran on a fork PR but no comment appeared

This is expected and handled gracefully. GitHub issues pull requests **from forks** a **read-only `GITHUB_TOKEN`** by design, so the comment API returns `403` no matter what `permissions:` your workflow grants — a permissions block cannot override the fork-token downgrade.

When this happens Delimit writes the **exact same governance report to the job summary** (the "Summary" tab of the run), which is always writable. Your finding stays visible on the run page; the action never fails over a blocked comment (advisory by default).

If you specifically want inline PR comments on fork PRs, the [`pull_request_target`](https://docs.github.com/actions/using-workflows/events-that-trigger-workflows#pull_request_target) event runs with a writable token — but it executes in the **base-repo context** and can be unsafe with untrusted PR code. Adopt it only after reviewing GitHub's [preventing pwn requests](https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/) guidance. Same-repo (non-fork) PRs are unaffected and receive comments normally.

### Can I use this with JSON specs?

Yes. Delimit supports both YAML (`.yaml`, `.yml`) and JSON (`.json`) spec files. Set the input paths accordingly.

### Can I use this in a monorepo with multiple specs?

Yes. Add multiple Delimit steps, each with different `old_spec` / `new_spec` pairs:

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    old_spec: base/services/users/openapi.yaml
    new_spec: services/users/openapi.yaml

- uses: delimit-ai/delimit-action@v1
  with:
    old_spec: base/services/billing/openapi.yaml
    new_spec: services/billing/openapi.yaml
```

### Advisory mode still shows errors in the PR comment — is that expected?

Yes. Advisory mode reports everything (including errors) in the PR comment and GitHub annotations, but it always exits with code `0` so your CI stays green. Switch to `enforce` mode when you want breaking changes to block the merge.

### How is the semver bump calculated?

The classification is deterministic:
- **major** — any breaking change detected (endpoint removed, required param added, field removed, type changed, etc.)
- **minor** — additive changes only (new endpoints, optional fields, enum values added)
- **patch** — non-functional changes only (description updates)
- **none** — no changes detected

---

## CLI

For local development, pre-commit checks, and CI/CD pipelines outside GitHub Actions, use the [Delimit CLI](https://www.npmjs.com/package/delimit-cli):

```bash
npm install -g delimit-cli
delimit lint api/openapi.yaml
delimit diff old-api.yaml new-api.yaml
delimit explain old-api.yaml new-api.yaml --template migration
```

---

## Pricing

The Action itself is free and open source (MIT). The free tier covers public repos with advisory mode, signed attestation, and the full 28-type breaking change classifier.

For teams that want enforcement, governance dashboards, custom policies under multi-model review, and audit-ready trust pages:

- **Pro** ($10/mo): unlimited deliberation, security audit, test verification, policy gating, agent orchestration.
- **Premium** ($50-100/mo): priority support, team features, attestation history.
- **Enterprise**: custom. Contact us via [delimit.ai/pricing](https://delimit.ai/pricing).

The action requires no signup. Pro and Premium are managed at [delimit.ai/pricing](https://delimit.ai/pricing).

---

## Links

- [Delimit CLI on npm](https://www.npmjs.com/package/delimit-cli) - Local development tool
- [Worked examples](https://delimit.ai/reports) - Full attestation reports against public API specs
- [Methodology](https://delimit.ai/methodology/mcp-attestation) - How signing and replay work
- [Pricing](https://delimit.ai/pricing) - Free, Pro, Premium, Enterprise
- [GitHub Repository](https://github.com/delimit-ai/delimit-action) - Source code and issues
- [GitHub Action Marketplace](https://github.com/marketplace/actions/delimit-merge-gate-for-ai-written-code) - Install from Marketplace

---

## License

MIT