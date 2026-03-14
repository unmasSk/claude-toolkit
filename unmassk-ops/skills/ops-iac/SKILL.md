---
name: ops-iac
description: >
  Use when the user asks to "generate Terraform", "validate Terraform",
  "scaffold Terragrunt", "validate Terragrunt", "create Ansible playbook",
  "validate Ansible", "lint infrastructure code", "security scan IaC",
  "check Terraform best practices", "scan IaC for vulnerabilities",
  "create Terraform module", "validate HCL", "run checkov",
  or mentions any of: Terraform, Terragrunt, Ansible, HCL, .tf, .tfvars,
  playbook, role, inventory, infrastructure as code, IaC, checkov, tflint,
  ansible-lint, terraform validate, terraform plan, terraform init,
  terraform fmt, terragrunt run, terragrunt hcl fmt, FQCN, ansible-vault,
  provider, module, state, backend, resource block, data source.
  Use this for generating production-ready Terraform modules with provider
  pinning and security hardening, validating existing .tf files through a
  full pipeline (format, lint, validate, Checkov security scan, secret
  detection, version consistency), scaffolding Terragrunt DRY configurations
  for multi-environment deployments (stacks, feature flags, exclude blocks),
  creating Ansible playbooks and roles with FQCN enforcement and vault-based
  secret management, and running automated security audits on any IaC
  codebase. Includes 20 scripts (bash and Python) that call real tools
  (terraform, tflint, checkov, ansible-lint, yamllint, molecule) with
  graceful fallback when tools are missing. 14 reference files provide
  best practices, common error catalogs, security checklists, and pattern
  libraries for Terraform, Terragrunt, and Ansible.
  Based on cc-devops-skills by akin-ozer (Apache-2.0).
version: 1.0.0
---

# IaC -- Infrastructure as Code Toolkit

Generation and validation for Terraform, Terragrunt, and Ansible.

## What this skill covers

- **Terraform**: generate modules, validate HCL, security scan, lint, CI/CD pipelines
- **Terragrunt**: scaffold DRY configurations, validate inputs, run multi-module operations
- **Ansible**: generate playbooks and roles, validate, lint, security scan

## Routing Table

Read the reference(s) that match the task before doing anything else.

### Terraform tasks

| Task | Read these references |
|------|----------------------|
| Generate new Terraform code | `terraform-best-practices.md`, `terraform-common-patterns.md` |
| Generate provider-specific resources | `terraform-provider-examples.md` |
| Validate or lint | `terraform-validation-best-practices.md` |
| Security scan | `terraform-security-checklist.md` |
| Debug errors | `terraform-common-errors.md` |
| Use Terraform 1.10+ features (ephemeral, write-only, actions, query) | `terraform-advanced-features.md` |

### Terragrunt tasks

| Task | Read these references |
|------|----------------------|
| Scaffold new Terragrunt config | `terragrunt-best-practices.md`, `terragrunt-common-patterns.md` |
| Validate Terragrunt | `terragrunt-best-practices.md` |
| Generate stacks, feature flags, exclude blocks (0.78+/0.93+) | `terragrunt-common-patterns.md` |

### Ansible tasks

| Task | Read these references |
|------|----------------------|
| Generate playbook or role | `ansible-best-practices.md`, `ansible-module-patterns.md` |
| Find correct module / fix deprecated usage | `ansible-module-alternatives.md` |
| Security scan | `ansible-security-checklist.md` |
| Debug errors | `ansible-common-errors.md` |

---

## Workflows

### Terraform: generate → validate → scan → report

1. **Generate** — Read `terraform-best-practices.md` and `terraform-common-patterns.md`. Write HCL.
2. **Format** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/terraform-ci-checks.sh <dir>
   ```
3. **Extract info** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/extract_tf_info_wrapper.sh <dir>
   ```
4. **Security scan** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/run_checkov.sh <dir>
   ```
5. **Secret scan** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/scan_secrets.sh <dir>
   ```
6. **Version consistency** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/check_feature_version_consistency.sh <dir>
   ```
7. Fix all findings. Report: findings count, severity breakdown, actions taken.

### Terragrunt: scaffold → validate → report

1. **Scaffold** — Read `terragrunt-best-practices.md` and `terragrunt-common-patterns.md`. Write HCL.
2. **Validate** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_terragrunt.sh <dir>
   ```
3. Fix all findings. Report: issues found, actions taken.

### Ansible: generate → validate → security → report

1. **Generate** — Read `ansible-best-practices.md` and `ansible-module-patterns.md`. Write YAML.
2. **Check FQCN** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/check_fqcn.sh <playbook-or-dir>
   ```
3. **Validate playbook** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_playbook.sh <playbook>
   ```
   Or for a role:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_role.sh <role-dir>
   ```
4. **Validate inventory** (if applicable) — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_inventory.sh <inventory>
   ```
5. **Security scan** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_playbook_security.sh <playbook>
   ```
   Or for a role:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/validate_role_security.sh <role-dir>
   ```
6. **Extract info** — Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/extract_ansible_info_wrapper.sh <dir>
   ```
7. Fix all findings. Report: findings count, severity breakdown, actions taken.

---

## Tool setup

If a required tool (checkov, ansible-lint, tflint, etc.) is not installed:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/install_checkov.sh
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/ansible-setup-tools.sh
```

For Ansible role testing with Molecule:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/test_role.sh <role-dir>
```

To detect custom Ansible resources:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/detect_custom_resources.py <dir>
```

---

## Script reference

All scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/ops-iac/scripts/`. Use them — do not skip them to report a result manually.

| Script | Purpose |
|--------|---------|
| `terraform-ci-checks.sh` | fmt check + validate + tflint for a Terraform directory |
| `extract_tf_info_wrapper.sh` | Extract resource/provider/module inventory |
| `extract_tf_info.py` | Python implementation of TF info extraction |
| `run_checkov.sh` | Run Checkov security scan on Terraform/HCL |
| `install_checkov.sh` | Install or upgrade Checkov |
| `scan_secrets.sh` | Scan for hardcoded secrets |
| `check_feature_version_consistency.sh` | Verify TF feature flags match required_version |
| `validate_terragrunt.sh` | Validate Terragrunt HCL and inputs |
| `terragrunt-ci-checks.sh` | CI checks for Terragrunt configurations |
| `validate_playbook.sh` | Syntax check + ansible-lint for a playbook |
| `validate_playbook_security.sh` | Security-focused validation of a playbook |
| `validate_role.sh` | Validate an Ansible role |
| `validate_role_security.sh` | Security-focused validation of a role |
| `validate_inventory.sh` | Validate an Ansible inventory file |
| `check_fqcn.sh` | Detect non-FQCN module usage in playbooks/roles |
| `ansible-setup-tools.sh` | Install ansible-lint and related tools |
| `extract_ansible_info_wrapper.sh` | Extract playbook/role inventory info |
| `extract_ansible_info.py` | Python implementation of Ansible info extraction |
| `detect_custom_resources.py` | Detect custom Ansible resource definitions |
| `test_role.sh` | Run Molecule tests for a role |

---

## Mandatory rules

- Always run the scripts. Never skip validation to save time.
- Always read the routing table reference before generating code.
- Never use deprecated Ansible short names — always FQCN (`ansible.builtin.*`).
- Never hardcode secrets in any IaC file.
- For Terragrunt 0.93+: use `run --all` not `run-all`, use `hcl fmt` not `hclfmt`.
- Mark sensitive Terraform variables with `sensitive = true`.
- Always pin provider and module versions.

---

## Done criteria

A task is complete when:
- All scripts ran with no unresolved findings
- No hardcoded secrets in output
- Provider/module versions are pinned
- Ansible modules use FQCN
- Report delivered: tool used, findings count, severity, actions taken
