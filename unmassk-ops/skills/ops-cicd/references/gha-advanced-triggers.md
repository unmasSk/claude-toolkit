# Advanced GitHub Actions Triggers

## workflow_run

Chains workflows. Recommended for secure post-CI processing of external PRs.

```yaml
# deploy.yml -- runs after CI completes on main
on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types: [completed]
    branches: [main]

jobs:
  deploy:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/download-artifact@c850b930e6ba138125429b7e5c93fc707a7f8427 # v4.1.4
        with:
          name: build-artifacts
          run-id: ${{ github.event.workflow_run.id }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

Available context: `.workflow_run.name`, `.conclusion`, `.head_sha`, `.head_branch`, `.id`, `.event`

### Security comparison

| Trigger | Context | Secrets | Safe? |
|---|---|---|---|
| `pull_request` | PR branch | No | Yes |
| `pull_request_target` | Target branch | Yes | Dangerous for external PRs |
| `workflow_run` | Target branch | Yes | Yes (if used correctly) |

---

## repository_dispatch

Triggers workflows from external systems via the GitHub API.

```yaml
on:
  repository_dispatch:
    types: [deploy-prod, deploy-staging, run-migration]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Parse payload
        run: |
          echo "Version: ${{ github.event.client_payload.version }}"
          echo "Requestor: ${{ github.event.client_payload.requestor }}"
```

Trigger via API:
```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/REPO/dispatches \
  -d '{"event_type":"deploy-prod","client_payload":{"version":"v1.2.3"}}'
```

Always validate `client_payload` fields before use:
```yaml
- run: |
    ENV="${{ github.event.client_payload.environment }}"
    if [[ ! "$ENV" =~ ^(dev|staging|production)$ ]]; then
      echo "Invalid environment: $ENV"
      exit 1
    fi
```

---

## issue_comment (ChatOps)

Trigger workflows from PR comments. Security is critical.

```yaml
on:
  issue_comment:
    types: [created]

jobs:
  deploy:
    if: |
      github.event.issue.pull_request &&
      startsWith(github.event.comment.body, '/deploy') &&
      contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association)
    permissions:
      contents: read
      pull-requests: write
    runs-on: ubuntu-latest
```

Author association levels: `OWNER`, `MEMBER`, `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `NONE`

Security rules for ChatOps:
- Always check `github.event.issue.pull_request` (ensures it's a PR, not an issue).
- Always check `author_association`.
- Never pass comment body to shell without parsing and validation.
- Pass via `env:`, never inline.

---

## Path Filtering

```yaml
on:
  push:
    paths:
      - 'src/**'
      - 'lib/**/*.js'
      - '!src/**/*.md'      # exclude
      - '!**/__tests__/**'
  pull_request:
    paths:
      - 'packages/frontend/**'
      - 'packages/shared/**'
      - '!packages/**/README.md'
```

---

## pull_request vs pull_request_target

```yaml
# Safe for PR validation (no secrets access)
on:
  pull_request:
    branches: [main]

# Dangerous for external PRs -- secrets accessible
on:
  pull_request_target:
    branches: [main]
# ONLY use pull_request_target if you do NOT checkout PR code
# Safe use: posting PR comments from target branch code
```

---

## Trigger Selection Guide

| Scenario | Trigger |
|---|---|
| Standard PR validation | `pull_request` |
| External PR + secrets needed | `workflow_run` after `pull_request` |
| Deploy after CI | `workflow_run` |
| External system trigger | `repository_dispatch` |
| ChatOps slash commands | `issue_comment` |
| Scheduled cleanup | `schedule` |
