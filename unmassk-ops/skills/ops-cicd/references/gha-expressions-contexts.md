# GitHub Actions Expressions and Contexts

## Expression Syntax

```yaml
# Explicit (required in env, with, name, outputs)
env:
  VALUE: ${{ github.sha }}

# Implicit (if conditions evaluate expressions automatically)
if: github.ref == 'refs/heads/main'
if: ${{ github.ref == 'refs/heads/main' }}   # equivalent
```

Expressions are evaluated before jobs run on the runner.

## Key Contexts

### github
```yaml
${{ github.event_name }}                          # push, pull_request, schedule, ...
${{ github.event.action }}                        # opened, synchronize, ...
${{ github.repository }}                          # owner/repo
${{ github.ref }}                                 # refs/heads/main
${{ github.ref_name }}                            # main
${{ github.sha }}                                 # full commit SHA
${{ github.actor }}                               # username that triggered run
${{ github.run_id }}                              # unique run ID
${{ github.run_number }}                          # incrementing run number
${{ github.event.pull_request.number }}
${{ github.event.pull_request.title }}
${{ github.event.pull_request.head.sha }}
${{ github.event.head_commit.message }}
```

### runner
```yaml
${{ runner.os }}      # Linux, Windows, macOS
${{ runner.arch }}    # X64, ARM64
${{ runner.temp }}    # temp directory
```

### secrets
```yaml
env:
  API_KEY: ${{ secrets.API_KEY }}
```

### steps
```yaml
steps:
  - id: tests
    run: npm test

  - if: steps.tests.outcome == 'success'
    run: ./upload.sh

  - run: echo "Result: ${{ steps.tests.outputs.result }}"
```

Step properties: `.outcome`, `.conclusion`, `.outputs.<name>`

### matrix
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    node: [20, 22, 24]

# Reference
runs-on: ${{ matrix.os }}
node-version: ${{ matrix.node }}
```

### inputs (workflow_dispatch / workflow_call)
```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        type: choice
        options: [dev, staging, production]

# Reference
if: inputs.environment == 'production'
```

## Functions

### String
```yaml
contains(github.ref, 'refs/tags/')
startsWith(github.ref, 'refs/tags/v')
endsWith(github.event.pull_request.head.ref, '-hotfix')
format('Building {0} on {1}', github.ref_name, runner.os)
```

### Type conversion
```yaml
toJSON(github)                             # object → JSON string
fromJSON('{"versions":[18,20,22]}')        # JSON string → object
```

### Hash
```yaml
hashFiles('**/package-lock.json')          # cache key generation
hashFiles('**/*.go', '**/go.sum')          # multiple patterns
```

### Status
```yaml
success()     # previous steps succeeded
failure()     # any previous step failed
always()      # regardless of status
cancelled()   # workflow was cancelled
```

## Operators

```yaml
# Comparison
if: github.ref == 'refs/heads/main'
if: runner.os != 'Windows'

# Logical
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
if: github.event_name == 'push' || github.event_name == 'pull_request'
if: "!(github.event_name == 'pull_request')"

# Numeric
if: github.event.pull_request.changed_files < 10
```

Precedence: `()` > `!` > `<,<=,>,>=` > `==,!=` > `&&` > `||`

## Common Patterns

```yaml
# Branch conditions
if: github.ref == 'refs/heads/main'
if: startsWith(github.ref, 'refs/tags/v')

# PR events
if: |
  github.event_name == 'pull_request' &&
  (github.event.action == 'opened' || github.event.action == 'synchronize')

# Skip CI
if: "!contains(github.event.head_commit.message, '[skip ci]')"

# Dynamic environment name
environment: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}

# Default value
environment: ${{ inputs.environment || 'dev' }}
```

## Security Rule

Never interpolate untrusted input directly in `run:`. Always use `env:`.

```yaml
# Unsafe
- run: echo "${{ github.event.pull_request.title }}"

# Safe
- env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: echo "$PR_TITLE"
```
