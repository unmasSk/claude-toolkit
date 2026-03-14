# Modern GitHub Actions Features

## Job Summaries

Write markdown to `$GITHUB_STEP_SUMMARY` to display rich output in the Actions UI.

```yaml
- name: Test summary
  if: always()
  run: |
    echo "## Test Results" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "| Suite | Status |" >> $GITHUB_STEP_SUMMARY
    echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY
    echo "| Unit | Passed |" >> $GITHUB_STEP_SUMMARY
    echo "| Coverage | ${{ steps.test.outputs.coverage }}% |" >> $GITHUB_STEP_SUMMARY
```

Collapsible details:
```yaml
- run: |
    echo "<details><summary>Full output</summary>" >> $GITHUB_STEP_SUMMARY
    cat test-output.txt >> $GITHUB_STEP_SUMMARY
    echo "</details>" >> $GITHUB_STEP_SUMMARY
```

---

## Deployment Environments

```yaml
jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: https://staging.example.com
    steps:
      - run: ./deploy.sh staging

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://example.com
    steps:
      - run: ./deploy.sh production
```

Dynamic environment:
```yaml
environment:
  name: ${{ github.ref_name == 'main' && 'production' || 'staging' }}
  url: ${{ github.ref_name == 'main' && 'https://example.com' || 'https://staging.example.com' }}
```

Configure protection rules in repository Settings > Environments: required reviewers, wait timer, deployment branches.

---

## Container Jobs

Run jobs inside Docker for consistent, isolated environments.

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    container:
      image: node:20-alpine
      options: --cpus 2 --memory 4g

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s

    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Run tests
        env:
          DATABASE_URL: postgres://postgres:postgres@postgres:5432/test
          REDIS_URL: redis://redis:6379
        run: npm test
```

Always use specific image tags, never `latest`. Configure health checks for services.

---

## Workflow Annotations

Create notices, warnings, and errors in the Actions UI and PR Files tab.

```yaml
- run: |
    # Simple annotations
    echo "::notice::Build completed"
    echo "::warning::Deprecated API usage detected"
    echo "::error::Configuration missing"

    # File/line annotations (appear in PR Files tab)
    echo "::error file=src/app.js,line=10::Type mismatch"
    echo "::warning file=config.js,line=23::Deprecated option"
```

Log groups (collapse verbose output):
```yaml
- run: |
    echo "::group::Installing dependencies"
    npm ci
    echo "::endgroup::"
```

Mask a value:
```yaml
- run: |
    SENSITIVE="$(./get-secret.sh)"
    echo "::add-mask::$SENSITIVE"
```

All workflow commands:
| Command | Purpose |
|---|---|
| `::notice::` | Info annotation |
| `::warning::` | Warning annotation |
| `::error::` | Error annotation (does not fail step) |
| `::group::` | Start collapsed section |
| `::endgroup::` | End collapsed section |
| `::add-mask::` | Mask value in logs |
| `::debug::` | Debug message (requires debug logging enabled) |

---

## Reusable Workflows (Limits 2025)

- Up to 10 nesting levels (previously 4).
- Up to 50 workflows per run (previously 20).

```yaml
# Reusable workflow
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      deploy-token:
        required: true
    outputs:
      deployment-url:
        description: "Deployment URL"
        value: ${{ jobs.deploy.outputs.url }}
```
