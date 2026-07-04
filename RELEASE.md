# Release Path — delimit-ai/delimit-action

This document describes the **single intended release path** for the Delimit GitHub
Action. It exists because the published floating `v1` tag is a **production surface for
every consumer** (`uses: delimit-ai/delimit-action@v1`), and releases must never drift
away from the audited `main` branch again.

> Status: DRAFT for founder review (STR-2169 / DRAFT-D5). Uncommitted working-tree file.

## Source of truth

- **Branch:** `main` on `github.com/delimit-ai/delimit-action`. All releases ship from
  a commit that is on `main`. Nothing is ever released from a detached, unpushed, or
  side-branch tree.
- **Local checkout must equal `origin/main`** before any release action. Verify with:
  ```bash
  git fetch --all --tags
  git rev-parse HEAD origin/main   # must match
  git status --porcelain           # must be empty
  ```

## Tag model

Two kinds of tags, with different rules:

1. **Immutable semver tags — `vX.Y.Z`** (e.g. `v1.11.4`).
   - Created once, never moved.
   - Pushing a `v*` tag triggers `.github/workflows/release.yml`, which builds a source
     tarball (`git archive HEAD`), a CycloneDX SBOM, a keyless Sigstore signature
     (Rekor-logged), and an SLSA build-provenance attestation, then publishes a GitHub
     Release with those four artifacts.
   - `v1-current` is a bookmark that tracks the latest cut semver commit.

2. **Floating major tag — `v1`** (and `v0`).
   - This is what consumers pin. Moving it re-points **every** downstream workflow.
   - It is moved **manually** to the tip commit of an already-released semver tag on
     `main`. There is no automation that advances `v1`; the `release.yml` workflow does
     NOT move it.

## Moving the floating `v1` tag = a production deploy

Per the 2026-04-07 ruleset-bypass postmortem, force-updating a floating tag on a public
repo is equivalent to deploying to every consumer. Therefore, re-pointing `v1`:

- Is **founder-gated** — explicit approval at the moment of the tag push, not
  retroactively, and not covered by any prior "cut the release" approval.
- Must run the **full deploy-gate chain** first:
  `delimit_security_audit` → `delimit_test_smoke` → `delimit_changelog` → `delimit_deploy_plan`.
  Unit tests passing is NOT a substitute for the security audit.
- Is **never** done by an autonomous session, and **never** from the `crypttrx`
  account — all delimit-ai org actions go through `infracore`.

### Intended sequence to release a new version

```
1. Land changes on main via PR (branch protection / review as configured).
2. Fast-forward local main to origin/main; confirm clean tree.
3. Cut an immutable semver tag on the release commit:
     git tag v1.X.Y <commit-on-main> && git push origin v1.X.Y
   -> release.yml runs, publishes the signed GitHub Release.
4. FOUNDER GATE + deploy-gate chain. Only then, move the floating v1:
     git tag -f v1 v1.X.Y && git push --force origin v1
   (This step is the production deploy. Do not perform it autonomously.)
5. Update v1-current to the same commit.
```

## Known drift finding (2026-07, DRAFT-D5 reconciliation)

At reconciliation time the state was:

- Local checkout HEAD was `70048c2` (2026-05-25) — a **month behind** the published
  `v1`. It has been fast-forwarded to `origin/main` = `ccf7f46`.
- The floating `v1` points at `9cc52e7` (2026-06-18, "zero-config secret scan", PR #27).
- The last **immutable semver** tag is `v1.11.4` = `v1-current` = `3f0eb56`
  (2026-06-04) — which is **2 commits behind** `v1`.
- `main` (`ccf7f46`) is **3 commits ahead** of `v1`.

**Implication:** `v1` was advanced past the last semver tag without cutting a matching
`v1.12.x` release, so the floating tag currently has **no corresponding immutable
versioned tag or signed GitHub Release** at `9cc52e7`. This should be reconciled by
cutting the missing semver tag at the `v1` commit (or by deciding the next release
supersedes it) — a founder-gated step, not performed here.

**No tag was moved, deleted, or re-pointed during this reconciliation. All work was
read-only against tags; only the local `main` branch pointer was fast-forwarded to
`origin/main`.**
