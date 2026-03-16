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

## Security Best Practices

When using the Delimit GitHub Action:

1. **Never commit API keys or tokens** to your repository
2. **Use GitHub Secrets** for sensitive configuration
3. **Pin the action version** in your workflows (e.g., `delimit-ai/delimit-action@v1`)
4. **Review PR annotations** before merging

## Data Privacy

The Delimit GitHub Action processes your API specifications within the GitHub Actions runner. Your specs are not sent to external servers.
