# act Usage Reference

act (nektos/act) runs GitHub Actions workflows locally using Docker.

## Installation

```bash
curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | bash

# Or via skill script
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gha-install-tools.sh
```

## Core Commands

```bash
# List all workflows
act -l

# List workflows for a specific event
act -l push
act -l pull_request

# Dry run (validate syntax without execution)
act -n
act --dryrun

# Run default workflow
act

# Run specific event
act push
act pull_request
act workflow_dispatch

# Run specific job
act -j build

# Run specific workflow file
act -W .github/workflows/ci.yml

# Verbose output
act -v
```

## Common Options

```bash
# Fix architecture on ARM Macs (M1/M2/M3)
act --container-architecture linux/amd64

# Use custom Docker image for a runner
act -P ubuntu-latest=node:18-buster

# Pass secrets
act -s GITHUB_TOKEN=ghp_xxx
act --secret-file .secrets

# Pass env vars
act --env MY_VAR=value

# Pass workflow_dispatch inputs
act workflow_dispatch --input myInput=myValue
```

## Configuration File (.actrc)

```bash
# Create in project root or home directory
--container-architecture=linux/amd64
--action-offline-mode
```

Options load order: XDG spec → HOME → current directory → CLI args.

## Exit Codes

- `0`: All jobs passed
- `1`: At least one job failed
- `2`: Workflow parsing or execution error

## Validation Use Case

The primary use case in this skill is syntax validation via dry-run:

```bash
# Catch syntax errors before pushing
act -n

# Validate specific workflow
act -n -W .github/workflows/ci.yml
```

## Limitations

- Not 100% compatible with GitHub's hosted runners.
- Requires Docker running locally.
- Actions that call the GitHub API may fail.
- Default runner images differ from GitHub's hosted runners.
- Secrets must be provided manually.
- Reusable workflows have limited local support.

## Troubleshooting

| Error | Fix |
|---|---|
| "Cannot connect to Docker daemon" | Start Docker Desktop |
| "Workflow file not found" | Run from repo root or use `-W` flag |
| "Action not found" | Use `-P` to specify alternative image or skip for validation only |
| "Out of disk space" | `docker system prune -a` |
