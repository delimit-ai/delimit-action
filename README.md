# Delimit GitHub Action

Detect breaking API changes in pull requests. Zero configuration required.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![GitHub Action](https://img.shields.io/badge/GitHub_Action-delimit--action-blue)

## Quick Start

```yaml
- uses: delimit-ai/delimit-action@v1
```

## What It Detects

### Breaking Changes (Will Fail CI)
- 🔴 **Endpoint removed** - Deleting any existing endpoint
- 🔴 **Required field removed** - Removing a required field from response
- 🔴 **Field type changed** - Changing type (e.g., string → number, integer → string)
- 🔴 **Required parameter added** - Adding new required parameters to existing endpoints
- 🔴 **Enum value removed** - Removing an existing enum value that clients may use
- 🔴 **Response field became required** - Changing optional response field to required
- 🔴 **Parameter type changed** - Changing parameter type (e.g., query → body, string → array)

### Safe Changes (Will Pass)
- ✅ **New endpoints added** - Adding new endpoints is always safe
- ✅ **Optional fields added** - Adding optional fields to requests or responses
- ✅ **Enum values added** - Adding new enum values (backward compatible)
- ✅ **Documentation changes** - Updates to descriptions, examples, etc.

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