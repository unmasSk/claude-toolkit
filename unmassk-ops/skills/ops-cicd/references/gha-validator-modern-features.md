# GitHub Actions Modern Features Validation Reference

## Reusable Workflows

Validation points:
- `workflow_call` trigger is present and correctly structured.
- Input types are valid: `string`, `number`, `boolean`.
- Required secrets are declared.
- Output references point to existing job outputs.

```yaml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      deploy-version:
        required: false
        type: string
        default: 'latest'
    secrets:
      deploy-token:
        required: true
    outputs:
      deployment-url:
        description: "Deployment URL"
        value: ${{ jobs.deploy.outputs.url }}
```

Limits (November 2025): 10 nesting levels, 50 workflows per run.

---

## OIDC Authentication

Validation points:
- `id-token: write` permission is set.
- `aws-region` or equivalent is provided.
- Audience claims match provider expectations.

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
      aws-region: us-east-1
```

OIDC token claims (November 2025): `repository`, `ref`, `sha`, `workflow`, `run_id`, `run_attempt`, `check_run_id` (new), `actor`, `environment`.

---

## SBOM and Build Provenance Attestations

Validation points:
- Required permissions: `id-token: write`, `attestations: write`, `contents: read`.
- Subject paths are valid.
- SBOM format is supported.

```yaml
permissions:
  id-token: write
  contents: read
  attestations: write

steps:
  - uses: actions/attest-sbom@v3
    with:
      subject-path: '${{ github.workspace }}/dist/*.tar.gz'
      sbom-path: 'sbom.spdx.json'

  - uses: actions/attest-build-provenance@v3
    with:
      subject-path: '${{ github.workspace }}/dist/*.tar.gz'
```

---

## Container Jobs

Validation points:
- Image tags are specific (not `latest`).
- Service health checks are configured.
- Volume mount syntax is correct.

```yaml
container:
  image: node:24
  env:
    NODE_ENV: test
  volumes:
    - /data:/data

services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: testdb
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

---

## Matrix Strategies

Validation points:
- Matrix values are arrays.
- Matrix variables are referenced correctly.
- `include`/`exclude` syntax is valid.

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    node: [20, 22, 24]
    exclude:
      - os: macos-latest
        node: 20
    include:
      - os: ubuntu-latest
        node: 24
        experimental: true
```

---

## Concurrency Control

Validation points:
- Group name uses valid expressions.
- `cancel-in-progress` is boolean or boolean expression.

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

---

## Job Summaries

`$GITHUB_STEP_SUMMARY` is a runtime feature. actionlint validates script syntax but not summary content. No static validation issues to check here.
