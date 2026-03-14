# actionlint Usage Reference

actionlint is a static checker for GitHub Actions workflow files.

## Installation

```bash
# Official script
bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)

# Or via skill script
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gha-install-tools.sh
```

## Core Usage

```bash
# Validate all workflows
actionlint

# Validate specific file
actionlint .github/workflows/ci.yml

# JSON output (for programmatic use)
actionlint -format '{{json .}}'

# SARIF output (for GitHub Code Scanning)
actionlint -format sarif
```

## Validation Categories

| Category | What it checks |
|---|---|
| Syntax | YAML structure, required fields, valid keys |
| Expressions | `${{ }}` syntax, type checking, function calls |
| Runner labels | Known GitHub-hosted runner names (typos caught) |
| Actions | Action exists, required inputs provided, no unknown inputs |
| Job dependencies | `needs:` references exist, no circular deps |
| CRON syntax | Schedule expressions validated |
| Shell scripts | Integrates shellcheck for `run:` steps |
| Glob patterns | Structural errors in `paths:` filters |
| Security | Script injection via untrusted input |

## Configuration

Create `.github/actionlint.yaml`:

```yaml
shellcheck:
  enable: true
  shell: bash

pyflakes:
  enable: true

ignore:
  - 'SC2086'

self-hosted-runner:
  labels:
    - my-custom-runner
    - gpu-runner
```

## Exit Codes

- `0`: No errors
- `1`: Validation errors found
- `2`: Fatal error (invalid file, config error)

## Common Errors and Fixes

### Runner typo
```yaml
# Error: Did you mean "ubuntu-latest"?
runs-on: ubuntu-lastest

# Fix
runs-on: ubuntu-latest
```

### Invalid CRON
```yaml
# Error: day of week must be 0-6
schedule:
  - cron: '0 0 * * 8'

# Fix
schedule:
  - cron: '0 0 * * 0'  # Sunday
```

### Undefined job in needs
```yaml
# Error: job "biuld" does not exist
needs: biuld

# Fix
needs: build
```

### Injection warning
```yaml
# Warning: potential script injection
run: echo ${{ github.event.issue.title }}

# Fix
env:
  TITLE: ${{ github.event.issue.title }}
run: echo "$TITLE"
```

## Notes

- `**.js` is NOT flagged by actionlint; use `**/*.js` for clarity anyway.
- `macos-13` runner was retired November 14, 2025 -- actionlint will warn.
- Cannot validate runtime behavior, only static analysis.
- Private actions cannot be validated (must be public).

## Pre-commit Integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/rhysd/actionlint
    rev: v1.7.9
    hooks:
      - id: actionlint
```

## CI Integration

```yaml
jobs:
  actionlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Download actionlint
        run: bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)
      - name: Run actionlint
        run: ./actionlint
```
