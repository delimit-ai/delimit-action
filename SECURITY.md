# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |

## Reporting a Vulnerability

We take security seriously at Delimit. If you discover a security vulnerability, please follow these steps:

1. **Do NOT** create a public GitHub issue
2. Email security@delimit.ai with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Your suggested fix (if any)

## Response Timeline

- **Acknowledgment**: Within 24 hours
- **Initial Assessment**: Within 72 hours
- **Fix Timeline**: Based on severity
  - Critical: Within 7 days
  - High: Within 14 days
  - Medium: Within 30 days
  - Low: Next release

## Threat model

We document the install-time and runtime threat surfaces separately because
developers evaluate them separately. The short version: **we never exfiltrate
your API spec, and we run inside your own CI runner with no outbound network
calls outside the GitHub Actions control plane.**

### Install-time surface

*What happens when your workflow pulls in `delimit-ai/delimit-action@v1`:*

- **Pinning:** pin to an immutable SHA (`@<sha>`) or a released major (`@v1`). Avoid `@main` in production.
- **No postinstall scripts.** The Action's package manifest does not run arbitrary shell on install.
- **Pinned dependency tree.** Each released version ships with a locked dependency graph (requirements.txt / package-lock.json); transitive versions are pinned.
- **SBOM published.** Each release attaches a CycloneDX SBOM (`sbom.cdx.json`) so you can diff the supply chain yourself.
- **Release signing.** Starting with v1.7.0, releases are **Sigstore/Cosign-signed** with provenance written to the public [Rekor transparency log](https://docs.sigstore.dev/logging/overview/). Verify with:
  ```bash
  cosign verify-blob \
    --certificate-identity-regexp "^https://github.com/delimit-ai/delimit-action/" \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
    --bundle <release-asset>.sigstore \
    <release-asset>
  ```

### Runtime surface

*What the Action does when it runs in your CI runner:*

- **Where it runs:** inside your GitHub Actions runner (ephemeral VM). No hosted Delimit service is in the path.
- **What it reads:**
  - The OpenAPI / JSON-schema file path you pass via `spec:` input.
  - The base branch's copy of the same file (via `actions/checkout`).
  - Optional policy file at `.delimit/policies.yml`.
  - `$GITHUB_TOKEN` — used only to post the PR comment via GitHub API.
- **What it writes:**
  - A single PR comment on the PR that triggered the run (or updates the existing Delimit comment).
  - A JSON governance report at `/tmp/delimit_report.json` inside the runner (discarded when the runner is destroyed).
- **Outbound network calls:**
  - `api.github.com` for posting the PR comment (via `$GITHUB_TOKEN`).
  - `pypi.org` / `registry.npmjs.org` for the install-time dependency resolution (controlled by GitHub Actions).
  - **No calls to any delimit.ai endpoint.** Your API spec is never transmitted to a Delimit-operated service.
- **Optional `Learn more` link:** when a breaking change is detected, the PR comment includes a link to `https://delimit.ai/action-help` with URL parameters (repo, PR number, top change type) that are already part of the public PR surface. The Action does not make this request itself — the developer chooses to click.

### Explicitly out of scope

- The Action is **not** a code executor, secret scanner, dependency scanner, license scanner, or vulnerability scanner. Use dedicated tools for those.
- The Action is **not** a gate for non-OpenAPI / non-JSON-schema contracts (GraphQL, gRPC, etc.). It reads only the paths you pass.
- The Action does **not** mutate your repository. It only comments on PRs.

## Best practices when using the Action

1. **Never commit API keys or tokens** to your repository.
2. **Use GitHub Secrets** for sensitive configuration.
3. **Pin the action version** — a released major tag (`@v1`) or a specific SHA (`@<commit>`).
4. **Review PR annotations** before merging, especially in `mode: advisory`.
5. **Verify the Sigstore signature** on the release artifact if your compliance regime requires it.
6. **Grant `$GITHUB_TOKEN` minimum permissions** — only `contents: read` and `pull-requests: write` are needed.

## Data privacy

- The Delimit GitHub Action processes your API specifications **entirely within the GitHub Actions runner**. Your specs are not sent to external servers.
- The one outbound call to `api.github.com` is scoped to posting the PR comment using `$GITHUB_TOKEN` — nothing else.
- The optional `Learn more` link embedded in a PR comment contains only metadata that was already public (repo name + PR number + change-type label). It does not contain your spec contents. The link fires only when the developer chooses to click it.
