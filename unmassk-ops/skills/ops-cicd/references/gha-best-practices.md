# GitHub Actions Best Practices

## Security

### Pin actions to full SHA

```yaml
# Recommended
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

# Acceptable for official GitHub actions only
- uses: actions/checkout@v4

# Never
- uses: actions/checkout@main
- uses: actions/checkout@latest
```

### Minimal permissions

```yaml
permissions:
  contents: read   # top-level default: read-only

jobs:
  deploy:
    permissions:
      contents: read
      packages: write
      pull-requests: write
```

### Secrets

```yaml
# Pass via env, never inline
- name: Deploy
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: |
    echo "::add-mask::$API_KEY"
    ./deploy.sh

# Never
- run: echo "API_KEY=${{ secrets.API_KEY }}"
```

### Injection prevention

Untrusted input (PR titles, issue bodies, comment text) must go through env vars.

```yaml
# Safe
- name: Check PR title
  env:
    TITLE: ${{ github.event.pull_request.title }}
  run: |
    if [[ ! "$TITLE" =~ ^feat ]]; then exit 1; fi

# Unsafe -- injection risk
- run: echo "${{ github.event.pull_request.title }}" | grep "fix"
```

### Dependency review

```yaml
jobs:
  dependency-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: critical
          allow-licenses: MIT, Apache-2.0, BSD-3-Clause
```

---

## Performance

### Caching

Use built-in cache where available; fall back to `actions/cache@v5`.

```yaml
# Built-in (preferred)
- uses: actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238 # v6.2.0
  with:
    node-version: '24'
    cache: 'npm'
    cache-dependency-path: '**/package-lock.json'

# Manual cache
- uses: actions/cache@cdf6c1fa76f9f475f3d7449005a359c84ca0f306 # v5.0.3
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```

Cache notes (2025): repositories get 10 GB free; legacy cache service retired February 2025; use v5.0.3+.

### Concurrency

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

# Protect main from cancellation
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

### Shallow checkout

```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    fetch-depth: 1
```

### Matrix strategy

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    node: [20, 22, 24]
    exclude:
      - os: macos-latest
        node: 20
  fail-fast: false
  max-parallel: 4
```

---

## Workflow Design

### Job dependencies

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps: [...]

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps: [...]
```

### Timeouts (required on every job)

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Run tests
        timeout-minutes: 15
        run: npm test
```

### Reusable workflows

```yaml
# Caller
jobs:
  call-build:
    uses: ./.github/workflows/reusable-build.yml
    with:
      environment: production
    secrets:
      token: ${{ secrets.DEPLOY_TOKEN }}

# Reusable
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      token:
        required: true
    outputs:
      build-id:
        value: ${{ jobs.build.outputs.id }}
```

Reusable workflow limits (November 2025): up to 10 nesting levels, up to 50 workflows per run.

---

## Anti-Patterns

| Anti-pattern | Fix |
|---|---|
| `permissions: write-all` | Explicit minimal permissions per job |
| `uses: actions/checkout@main` | Pin to SHA |
| No `timeout-minutes` | Add timeout to every job |
| Inline `${{ github.event.pull_request.title }}` in `run:` | Pass via `env:` |
| `echo "KEY=${{ secrets.KEY }}"` | Never print secrets |
| `actions/cache@v1` | Upgrade to v5.0.3+ |
| `actions/checkout@v2/v3` | Upgrade to v6 (Node 24 runtime) |
