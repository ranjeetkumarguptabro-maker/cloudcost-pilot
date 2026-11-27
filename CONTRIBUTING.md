# Contributing to CloudCost Pilot

Thank you for your interest in contributing to **CloudCost Pilot**! We welcome contributions to help make cloud cost monitoring and optimization accessible, automated, and explainable.

---

## Code of Conduct & Core Principles

1. **Read-Only First**: CloudCost Pilot is designed as a read-only monitoring and optimization platform. We never introduce automatic resource deletion, termination, or destructive AWS API calls.
2. **Explainable Recommendations**: Any optimization suggestions must be backed by quantifiable metrics and transparent logic.
3. **High Code Quality**: All contributions must adhere to strict PEP 8 formatting (88-character limit enforced via Ruff) and include thorough unit test coverage.

---

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/ranjeetkumarguptabro-maker/cloudcost-pilot.git
cd cloudcost-pilot
```

### 2. Set up Python Environment

Python 3.12 is required:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]" || pip install ruff pytest pytest-cov boto3 botocore
```

---

## Quality Standards & Verification

Before submitting a pull request, ensure all linting, formatting, and unit tests pass:

```bash
# 1. Run Ruff linter
ruff check .

# 2. Verify code formatting
ruff format --check .

# 3. Execute all unit tests
pytest -v
```

---

## Submitting a Pull Request

1. Create a feature branch with a descriptive name:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with clear, structured commit messages. If collaborating, include appropriate `Co-authored-by:` trailers.
3. Push to your branch and open a Pull Request targeting the `main` branch.
4. Ensure the GitHub Actions CI pipeline passes all checks.
