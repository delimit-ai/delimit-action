# Contributing to Delimit Action

Thank you for your interest in contributing to the Delimit GitHub Action. We welcome contributions from the community.

## How to Contribute

### Reporting Issues

1. Check if the issue already exists
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce (include your workflow YAML if possible)
   - Expected vs actual behavior
   - GitHub Actions runner environment details

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `python3 -m pytest tests/`
5. Commit with clear messages
6. Push to your fork
7. Open a PR with:
   - Description of changes
   - Related issue numbers
   - Test results

## Development Setup

```bash
# Clone repository
git clone https://github.com/delimit-ai/delimit-action.git
cd delimit-action

# Install dependencies
pip install -r requirements.txt

# Run tests
python3 -m pytest tests/
```

## Testing

All PRs must:
- Pass existing tests
- Include tests for new features
- Not introduce regressions

## Areas for Contribution

- Documentation improvements
- Bug fixes
- New policy rules and presets
- Workflow examples
- Performance improvements

## Questions?

- Open a [Discussion](https://github.com/delimit-ai/delimit/discussions) on the main repo
- Email opensource@delimit.ai
