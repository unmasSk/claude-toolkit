# unmassk-ops

**DevOps toolkit covering infrastructure, containers, CI/CD, observability, and scripting.**

5 skills spanning the full DevOps lifecycle: Infrastructure as Code (Terraform, Terragrunt, Ansible), containers (Docker, Helm, Kubernetes), CI/CD pipelines (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins), observability (PromQL, LogQL, Loki, Fluent Bit), and scripting (Bash, Makefile).

Based on [cc-devops-skills](https://github.com/akin-ozer/cc-devops-skills) by akin-ozer (Apache-2.0).

## What's included

| Skill | References | Scripts | Covers |
|-------|-----------|---------|--------|
| `ops-iac` | 14 | 20 | Terraform, Terragrunt, Ansible |
| `ops-containers` | 19 | 22 | Docker, Helm, K8s, K8s Debug |
| `ops-cicd` | 30 | 30 | GitHub Actions, GitLab CI, Azure Pipelines, Jenkins |
| `ops-observability` | 9 | 10 | PromQL, LogQL, Loki, Fluent Bit |
| `ops-scripting` | 21 | 11 | Bash, Makefile |
| **Total** | **93** | **93** | |

## Quick start

Run `/plugin` in Claude Code and install `unmassk-ops` from the marketplace.

## Dependencies

Requires the **unmassk-crew** plugin for agent execution. Install it from the marketplace before using unmassk-ops.

## Scripts

All scripts use `${CLAUDE_PLUGIN_ROOT}` paths and run with `set -euo pipefail`. Scripts call real tools (terraform, tflint, checkov, ansible-lint, hadolint, kubeconform, actionlint, act, shellcheck, promtool) with graceful fallback when tools are missing.

## Audited by

- **Cerberus** — code review of all 93 scripts
- **Argus** — security audit of all 93 scripts
- **Ultron** — all findings fixed
- **Moriarty** — adversarial testing on IaC and Containers scripts
- **Yoda** — final production review (92/110)
