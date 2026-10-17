# CI/CD Workflows

This directory contains GitHub Actions workflows for continuous integration and deployment.

## Workflows

### 1. CI (`ci.yml`)

Main continuous integration workflow that runs on every push and pull request.

**Jobs:**
- **Lint**: Runs code quality checks
  - flake8 linting
  - bandit security scanning
  - black formatting check
  - isort import sorting check

- **Typecheck**: Runs type checking with mypy

- **Docs**: Builds Docusaurus on pushes and pull requests; broken site and Markdown links fail the job

- **Test**: Runs tests on multiple Python versions (3.10–3.13 on Ubuntu and macOS)
  - Uses pytest with coverage reporting
  - Uploads coverage to Codecov (on Python 3.11)

- **Build**: Builds and installs the package on pushes and pull requests
  - Creates distribution packages
  - Validates package with twine
  - Verifies installed CLI, schema access and wheel contents outside the checkout
  - Tests example and template configurations in the test job
  - Uploads artifacts for 7 days

**Triggers:**
- Push to `master`, `main`, or `develop` branches
- Pull requests to `master`, `main`, or `develop` branches
- Manual workflow dispatch

### 2. Publish (`publish.yml`)

Publishes the package to PyPI when a release is created.

**Features:**
- Uses trusted publishing (no API tokens needed)
- Validates package before publishing
- Can be triggered manually with version input

**Triggers:**
- Release published (GitHub release)
- Manual workflow dispatch

**Setup:**
1. Enable trusted publishing in PyPI:
   - Go to PyPI project settings
   - Add GitHub repository
   - Configure trusted publishing

2. Create a GitHub release:
   ```bash
   git tag v1.0.12
   git push origin v1.0.12
   ```
   Then create a release on GitHub with the same tag.

### 3. CodeQL Analysis (`codeql.yml`)

Security analysis using GitHub's CodeQL.

**Features:**
- Scans for security vulnerabilities
- Runs on schedule (weekly) and on push/PR
- Uses security-and-quality query suite

**Triggers:**
- Push to `master`, `main`, or `develop` branches
- Pull requests to `master`, `main`, or `develop` branches
- Weekly schedule (Sunday at midnight)
- Manual workflow dispatch

### 4. Deploy Documentation (`deploy-docs.yml`)

Builds the Docusaurus site in `docs/` and publishes it to GitHub Pages at
`https://ruarxive.org/apibackuper/`.

**Triggers:**
- Push to `master` or `main` that touches `docs/` or this workflow file
- Manual workflow dispatch

**Setup:** In repository **Settings → Pages**, set **Source** to **GitHub Actions**.
See `docs/GITHUB_PAGES_SETUP.md`.

### 5. Dependency Review (`dependency-review.yml`)

Reviews dependencies in pull requests for security vulnerabilities.

**Features:**
- Checks new dependencies for known vulnerabilities
- Fails on moderate or higher severity issues
- Only runs on pull requests

**Triggers:**
- Pull requests to `master`, `main`, or `develop` branches

## Usage

### Running Tests Locally

Before pushing, you can run the same checks locally:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run linting
flake8 apibackuper
bandit -r apibackuper -ll

# Check formatting
black --check apibackuper
isort --check-only apibackuper

# Type checking
mypy apibackuper --ignore-missing-imports --no-strict-optional

# Run tests
pytest --verbose --cov=apibackuper --cov-report=term-missing ./apibackuper ./tests
```

### Using Pre-commit Hooks

Install pre-commit hooks to run checks before committing:

```bash
pip install pre-commit
pre-commit install
```

Now checks will run automatically on `git commit`.

### Publishing a Release

1. Update the authoritative version in `pyproject.toml`, source-checkout version fallbacks in `apibackuper/__init__.py`, README and release notes; `setup.py` has been removed
2. Commit and push changes
3. Create a git tag:
   ```bash
   git tag v2.0.0
   git push origin v2.0.0
   ```
4. Create a GitHub release with the same tag
5. The publish workflow will automatically run

## Badges

Add these badges to your README.md (optional):

```markdown
![CI](https://github.com/yourusername/apibackuper/workflows/CI/badge.svg)
![CodeQL](https://github.com/yourusername/apibackuper/workflows/CodeQL%20Analysis/badge.svg)
[![codecov](https://codecov.io/gh/yourusername/apibackuper/branch/master/graph/badge.svg)](https://codecov.io/gh/yourusername/apibackuper)
```

## Troubleshooting

### Supported Python versions

The declared minimum is Python 3.10. Keep package metadata, tox and the CI matrix synchronized.

### Coverage Upload Fails

Codecov upload is optional and won't fail the build. Make sure you've connected your repository to Codecov.io.

### PyPI Publishing Fails

1. Ensure trusted publishing is configured in PyPI
2. Check that the version in `pyproject.toml` matches the release tag
3. Verify the package builds successfully locally
