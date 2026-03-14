# Common GitHub Actions Errors

## Syntax Errors

### Invalid YAML
```yaml
# Error: indentation
name:My Workflow
jobs:
build:
  runs-on: ubuntu-latest

# Fix
name: My Workflow
jobs:
  build:
    runs-on: ubuntu-latest
```

### Wrong event name
```yaml
# Error
on:
  pull-request:    # hyphen wrong

# Fix
on:
  pull_request:
```

## Expression Errors

### Incorrect expression syntax
```yaml
# Error: unrecognized named-value
if: github.ref == 'refs/heads/main'   # missing ${{ }}

# Fix (explicit)
if: ${{ github.ref == 'refs/heads/main' }}

# Fix (GitHub evaluates if conditions implicitly -- both forms valid)
if: github.ref == 'refs/heads/main'
```

### Type mismatch
```yaml
# Error: expected boolean, got string
if: ${{ 'true' }}

# Fix
if: ${{ true }}
if: ${{ success() }}
```

### Script injection warning
```yaml
# Warning: potential script injection
run: echo ${{ github.event.issue.title }}

# Fix
env:
  TITLE: ${{ github.event.issue.title }}
run: echo "$TITLE"
```

## Action Errors

### Action not found (typo)
```yaml
# Error
- uses: actions/chekout@v4

# Fix
- uses: actions/checkout@v4
```

### Deprecated action version
```yaml
# Warning: Node.js 12 (EOL April 2022)
- uses: actions/checkout@v2

# Warning: Node.js 16 (EOL September 2023)
- uses: actions/checkout@v3

# Current: Node.js 20+/24
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
```

## Job Configuration Errors

### Invalid runner label
```yaml
# Error
runs-on: ubuntu-lastest

# Valid labels
runs-on: ubuntu-latest
runs-on: ubuntu-24.04
runs-on: ubuntu-22.04
runs-on: windows-latest
runs-on: windows-2025
runs-on: macos-latest       # macOS 15 (Apple Silicon)
runs-on: macos-15
runs-on: macos-14
# RETIRED: macos-13 (retired November 14, 2025)
```

### Undefined job dependency
```yaml
# Error
deploy:
  needs: biuld    # typo

# Fix
deploy:
  needs: build
```

### Circular dependency
```yaml
# Error
job1:
  needs: job2
job2:
  needs: job1

# Fix: break the cycle
job1:
  runs-on: ubuntu-latest
job2:
  needs: job1
```

## Schedule Errors

### Invalid CRON
```yaml
# Error: day 8 doesn't exist (0-6 only)
schedule:
  - cron: '0 0 * * 8'

# Fix
schedule:
  - cron: '0 0 * * 0'   # Sunday

# Format: minute hour day-of-month month day-of-week
```

## Environment and Secrets

### Secret not found
- Verify secret is defined in repository Settings > Secrets.
- Check spelling (case-sensitive).
- Verify scope (repository, organization, or environment).

### Environment variable cross-OS
```yaml
# Works only on Linux/macOS
- run: echo $MY_VAR

# Cross-platform
- name: Print variable
  env:
    MY_VAR: ${{ secrets.MY_SECRET }}
  run: echo "$MY_VAR"          # Linux/macOS
  # run: echo $env:MY_VAR      # Windows PowerShell
```

## Matrix Errors

### Matrix not an array
```yaml
# Error
strategy:
  matrix:
    os: ubuntu-latest   # must be array

# Fix
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
```

## Debugging

### Enable debug logging

Set in repository Settings > Secrets:
- `ACTIONS_STEP_DEBUG` = `true` (detailed step logs)
- `ACTIONS_RUNNER_DEBUG` = `true` (runner diagnostic logs)

### Dump context
```yaml
- name: Dump context
  run: echo '${{ toJSON(github) }}'
```
