# Delimit GitHub Action

Detect breaking API changes in pull requests. Zero configuration required.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Quick Start

```yaml
- uses: delimit-ai/delimit-action@v1
```

## What It Detects

- 🔴 Removed endpoints
- 🔴 Deleted required fields
- 🔴 Type changes (string → number)
- 🔴 Breaking parameter modifications

## Installation

Add to `.github/workflows/api-check.yml`:

```yaml
name: API Breaking Change Check
on: pull_request

jobs:
  api-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: delimit-ai/delimit-action@v1
```

## Configuration

The action works with zero configuration - it automatically finds your OpenAPI/Swagger files.

### Optional Parameters

```yaml
- uses: delimit-ai/delimit-action@v1
  with:
    # Run in advisory mode (won't fail CI)
    advisory_mode: true
    
    # Specify OpenAPI file paths (auto-detected if not set)
    old_spec: api/openapi.yaml
    new_spec: api/openapi.yaml
```

## Examples

See the `examples/` directory for:
- `breaking-change-demo/` - Examples of breaking changes
- `safe-change-demo/` - Examples of safe changes

## License

MIT