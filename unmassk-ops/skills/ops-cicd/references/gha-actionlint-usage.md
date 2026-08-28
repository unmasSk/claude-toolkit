# actionlint Usage Reference

actionlint is a static checker for GitHub Actions workflow files.

> **Paths.** Every `scripts/…` path below is relative to this skill's own directory. To actually run one, resolve that directory in the same command — a shell variable does not survive from one call to the next:

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-ops/*/skills/ops-cicd' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/gha-install-tools.sh"
```

> If `$SKILL_DIR` comes back empty, the plugin is running from a checkout rather than an install: use the absolute path from the `Base directory for this skill:` line printed when this skill loaded. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

## Installation

```bash
# Official script
bash <(curl https://raw.githubusercontent.com/rhysd/actionlint/main/scripts/download-actionlint.bash)

# Or via skill script
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-ops/*/skills/ops-cicd' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/gha-install-tools.sh"
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
