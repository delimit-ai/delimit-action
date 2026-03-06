# Delimit GitHub Action

Official GitHub Action for [Delimit API Governance Platform](https://delimit.ai). Validate OpenAPI specifications in your CI/CD pipeline with enterprise-grade governance checks.

## Features

- 🛡️ **Privacy Shield™**: Sensitive data never leaves your GitHub runner
- ✅ **Automated Validation**: Check specs against governance rules on every PR
- 🚀 **Fast & Reliable**: Bundled dependencies for consistent performance
- 📊 **Structured Output**: Machine-readable results for advanced workflows
- 🔒 **Secure by Design**: API keys are masked in all logs

## Quick Start

```yaml
name: API Validation
on:
  pull_request:
    paths:
      - 'openapi.yaml'
      - 'api/*.yaml'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Validate OpenAPI Spec
        uses: delimit-ai/governance-action@v1
        with:
          api-key: ${{ secrets.DELIMIT_API_KEY }}
          spec-path: openapi.yaml
```

## Security

Your `DELIMIT_API_KEY` is a sensitive secret. To use it securely, store it as a [GitHub Encrypted Secret](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions) and pass it directly to the action.

### ✅ Do This
```yaml
- uses: delimit-ai/governance-action@v1
  with:
    api-key: ${{ secrets.DELIMIT_API_KEY }}
```

### ❌ Don't Do This
```yaml
# Never echo or print secrets
- run: echo "My key is ${{ secrets.DELIMIT_API_KEY }}"

# Never pass secrets through environment variables in run steps
- run: export KEY=${{ secrets.DELIMIT_API_KEY }} && some-command
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api-key` | **Yes** | - | Your Delimit API key from RapidAPI |
| `spec-path` | No | `openapi.yaml` | Path to the OpenAPI specification file |
| `command` | No | `validate` | CLI command to run (validate, diff, analyze) |
| `fail-on-warning` | No | `false` | Fail the action on warnings (not just errors) |
| `verbose` | No | `false` | Enable verbose output |

## Outputs

| Output | Description |
|--------|-------------|
| `valid` | Whether the specification is valid (`true` or `false`) |
| `error-count` | Number of validation errors found |
| `warning-count` | Number of validation warnings found |

## Examples

### Fail on Warnings

Enforce strict validation by failing on any warnings:

```yaml
- uses: delimit-ai/governance-action@v1
  with:
    api-key: ${{ secrets.DELIMIT_API_KEY }}
    spec-path: api/openapi.yaml
    fail-on-warning: true
```

### Multiple Spec Files

Validate multiple API specifications:

```yaml
strategy:
  matrix:
    spec: [users-api.yaml, payments-api.yaml, orders-api.yaml]

steps:
  - uses: actions/checkout@v4
  
  - uses: delimit-ai/governance-action@v1
    with:
      api-key: ${{ secrets.DELIMIT_API_KEY }}
      spec-path: specs/${{ matrix.spec }}
```

### Conditional Deployment

Only deploy if validation passes without warnings:

```yaml
- uses: delimit-ai/governance-action@v1
  id: validate
  with:
    api-key: ${{ secrets.DELIMIT_API_KEY }}
    spec-path: openapi.yaml

- name: Deploy API
  if: steps.validate.outputs.valid == 'true' && steps.validate.outputs.warning-count == '0'
  run: |
    echo "API validation passed with no warnings"
    # Your deployment script here
```

### PR Comment with Results

Post validation results as a PR comment:

```yaml
- uses: delimit-ai/governance-action@v1
  id: validate
  with:
    api-key: ${{ secrets.DELIMIT_API_KEY }}
    spec-path: openapi.yaml

- uses: actions/github-script@v6
  if: github.event_name == 'pull_request'
  with:
    script: |
      const valid = '${{ steps.validate.outputs.valid }}' === 'true';
      const errors = ${{ steps.validate.outputs.error-count }};
      const warnings = ${{ steps.validate.outputs.warning-count }};
      
      const status = valid ? '✅ Passed' : '❌ Failed';
      const body = `## API Validation ${status}
      
      - **Errors:** ${errors}
      - **Warnings:** ${warnings}
      
      ${!valid ? '⚠️ Please fix the validation errors before merging.' : ''}`;
      
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: body
      });
```

## Performance

This action uses bundled dependencies for optimal performance:
- No runtime dependency installation
- Consistent execution time (~2-5 seconds)
- Works offline after initial action download
- Deterministic results

## Privacy

The Privacy Shield™ technology ensures:
- API descriptions, examples, and server URLs are removed before validation
- Sensitive business logic never leaves your GitHub runner
- Only structural API information is sent for validation
- Full compliance with data protection requirements

## Troubleshooting

### API Key Issues

If you see "Invalid API key" errors:
1. Verify your secret is correctly set in repository settings
2. Ensure the secret name matches exactly (case-sensitive)
3. Check your API key is active on RapidAPI

### File Not Found

If the action can't find your spec file:
1. Ensure the file exists in your repository
2. Use the correct relative path from repository root
3. Check file permissions and case sensitivity

### Rate Limiting

If you hit rate limits:
1. Consider caching validation results for unchanged files
2. Validate only on specific file changes using path filters
3. Upgrade your RapidAPI plan for higher limits

## Support

- **Documentation**: https://api.delimit.ai/docs
- **Issues**: https://github.com/delimit-ai/governance-action/issues
- **Email**: support@delimit.ai
- **API Keys**: https://rapidapi.com/delimit/api/openapi-diff-api

## License

MIT © Delimit.ai

---

Built with ❤️ by the Delimit team