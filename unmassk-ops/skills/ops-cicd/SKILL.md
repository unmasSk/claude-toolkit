---
name: ops-cicd
description: >
  Use when the user asks to "generate GitHub Actions workflow",
  "validate GitHub Actions", "create GitLab CI pipeline",
  "validate GitLab CI", "generate Azure Pipelines",
  "validate Azure Pipelines", "create Jenkinsfile",
  "validate Jenkinsfile", "lint CI/CD config", "test workflow locally",
  "check action versions", "debug pipeline",
  or mentions any of: GitHub Actions, GitLab CI, Azure Pipelines,
  Jenkins, Jenkinsfile, workflow, pipeline, .github/workflows,
  .gitlab-ci.yml, azure-pipelines.yml, actionlint, act,
  CI/CD, continuous integration, continuous delivery, job, stage,
  runner, self-hosted runner, matrix strategy, reusable workflow,
  composite action, OIDC, pipeline template.
  Use this for generating production-ready CI/CD pipelines across
  four platforms (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins),
  validating existing pipeline configs with real tools (actionlint, act),
  checking action versions and deprecations, testing workflows locally,
  generating Jenkinsfiles (declarative, scripted, shared libraries),
  and auditing pipeline security (secret exposure, injection risks,
  untrusted input handling). Includes 30 scripts (bash and Python)
  for automated validation and generation. 30 reference files provide
  best practices, common errors, security guidelines, syntax references,
  and platform-specific patterns.
  Based on cc-devops-skills by akin-ozer (Apache-2.0).
version: 1.0.0
---

# CI/CD -- Pipeline Generation and Validation Toolkit

## Scope

This skill covers CI/CD pipelines across four platforms: GitHub Actions, GitLab CI, Azure Pipelines, and Jenkins. It does NOT cover Terraform/Ansible (ops-iac) or Docker/Helm/Kubernetes (ops-containers).

---

## Platform Routing

| User request | Platform | Primary scripts |
|---|---|---|
| `.github/workflows/`, `workflow_call`, `actionlint`, `act` | GitHub Actions | `gha-validate-workflow.sh`, `gha-install-tools.sh` |
| `.gitlab-ci.yml`, `stages:`, `needs:`, `rules:` | GitLab CI | `gitlab-validate-ci.sh`, `gitlab-install-tools.sh` |
| `azure-pipelines.yml`, `stages/jobs/steps`, `task:` | Azure Pipelines | `azure-validate-pipelines.sh`, `azure-validate-syntax.py` |
| `Jenkinsfile`, `pipeline {}`, `node {}`, shared library | Jenkins | `jenkins-validate-jenkinsfile.sh`, `jenkins-generate-declarative.py` |

---

## MANDATORY Script Commands

All paths use `${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/`.

### GitHub Actions

```bash
# 1. Install tools (actionlint + act) -- run once per environment
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gha-install-tools.sh

# 2. Validate a workflow file
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gha-validate-workflow.sh .github/workflows/ci.yml

# 3. Generate test scaffolding
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gha-test-generator.sh .github/workflows/ci.yml
```

### GitLab CI

```bash
# 1. Install tools
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gitlab-install-tools.sh

# 2. Validate pipeline
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gitlab-validate-ci.sh .gitlab-ci.yml

# 3. Validate syntax only
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gitlab-validate-syntax.py .gitlab-ci.yml

# 4. Check security
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gitlab-check-security.py .gitlab-ci.yml

# 5. Check best practices
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/gitlab-check-best-practices.py .gitlab-ci.yml
```

### Azure Pipelines

```bash
# 1. Validate pipeline
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/azure-validate-pipelines.sh azure-pipelines.yml

# 2. Validate syntax
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/azure-validate-syntax.py azure-pipelines.yml

# 3. Check security
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/azure-check-security.py azure-pipelines.yml

# 4. Check best practices
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/azure-check-best-practices.py azure-pipelines.yml

# 5. YAML lint
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/azure-yamllint-check.sh azure-pipelines.yml
```

### Jenkins

```bash
# 1. Validate Jenkinsfile
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-validate-jenkinsfile.sh Jenkinsfile

# 2. Validate declarative pipeline
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-validate-declarative.sh Jenkinsfile

# 3. Validate scripted pipeline
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-validate-scripted.sh Jenkinsfile

# 4. Validate shared library
bash ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-validate-shared-library.sh

# 5. Generate declarative Jenkinsfile
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-generate-declarative.py

# 6. Generate scripted Jenkinsfile
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-generate-scripted.py

# 7. Generate shared library
python3 ${CLAUDE_PLUGIN_ROOT}/skills/ops-cicd/scripts/jenkins-generate-shared-library.py
```

---

## Generation Workflow

For generating a new pipeline:

1. Identify platform from user request.
2. Read the platform reference file in `references/`.
3. Apply security rules first (secrets, image pinning, permissions).
4. Add reliability controls (timeouts, retries, dependencies).
5. Add performance improvements (caching, parallelism, shallow clone).
6. Run the validation script to confirm no errors.
7. Show the user the output before finalizing.

For validating an existing pipeline:

1. Run the platform's validation script.
2. Run the security check script.
3. Run the best-practices check script.
4. Report findings grouped by severity: Critical / Warning / Suggestion.

---

## Script Reference Table

| Script | Platform | Purpose |
|---|---|---|
| `gha-install-tools.sh` | GHA | Install actionlint and act |
| `gha-validate-workflow.sh` | GHA | Validate workflow with actionlint + act dry-run |
| `gha-test-generator.sh` | GHA | Generate test scaffolding for workflows |
| `gitlab-install-tools.sh` | GitLab | Install gitlab-ci-validator tools |
| `gitlab-validate-ci.sh` | GitLab | Full pipeline validation |
| `gitlab-validate-syntax.py` | GitLab | YAML syntax and keyword validation |
| `gitlab-check-security.py` | GitLab | Security audit (secrets, image pinning) |
| `gitlab-check-best-practices.py` | GitLab | Best practices check |
| `gitlab-python-wrapper.sh` | GitLab | Wrapper for Python validation scripts |
| `azure-validate-pipelines.sh` | Azure | Full pipeline validation |
| `azure-validate-syntax.py` | Azure | YAML syntax and schema validation |
| `azure-check-security.py` | Azure | Security audit |
| `azure-check-best-practices.py` | Azure | Best practices check |
| `azure-yamllint-check.sh` | Azure | YAML lint |
| `azure-python-wrapper.sh` | Azure | Wrapper for Python validation scripts |
| `azure-step-walker.py` | Azure | Walk and inspect pipeline steps |
| `azure-test-regressions.py` | Azure | Regression test runner |
| `jenkins-validate-jenkinsfile.sh` | Jenkins | Generic Jenkinsfile validation |
| `jenkins-validate-declarative.sh` | Jenkins | Declarative pipeline validation |
| `jenkins-validate-scripted.sh` | Jenkins | Scripted pipeline validation |
| `jenkins-validate-shared-library.sh` | Jenkins | Shared library validation |
| `jenkins-common-validation.sh` | Jenkins | Common validation utilities |
| `jenkins-best-practices.sh` | Jenkins | Best practices check |
| `jenkins-generate-declarative.py` | Jenkins | Generate declarative Jenkinsfile |
| `jenkins-generate-scripted.py` | Jenkins | Generate scripted Jenkinsfile |
| `jenkins-generate-shared-library.py` | Jenkins | Generate shared library skeleton |
| `jenkins-test-declarative.py` | Jenkins | Test declarative pipeline |
| `jenkins-test-shared-library.py` | Jenkins | Test shared library |
| `jenkins-lib/common_patterns.py` | Jenkins | Shared Jenkins patterns library |
| `jenkins-lib/syntax_helpers.py` | Jenkins | Groovy syntax helpers for Jenkinsfile generation |

---

## Mandatory Rules

**Security (non-negotiable):**
- No hardcoded secrets. Use platform secret stores: GHA `secrets.*`, GitLab CI/CD variables (masked+protected), Azure variable groups/service connections, Jenkins credentials binding.
- Pin versions: GHA actions to full SHA, GitLab images to specific tag or digest, Azure tasks to major version, Jenkins shared libs to tag.
- Minimal permissions: GHA `permissions:` block, GitLab protected environments, Azure service connection least privilege.
- No injection via untrusted input: always pass via env var, never inline `${{ github.event.pull_request.title }}` in `run:`.

**Generation:**
- Always include `timeout` / `timeout-minutes` for every job.
- Always include caching for package managers (npm, pip, maven, etc.).
- Never use `latest` tag for Docker images in CI.
- Use `rules:` not `only:/except:` in GitLab CI.
- Use `needs:` for DAG optimization in GitLab CI.
- Use `resource_group:` for deployment jobs in GitLab CI.
- Use `interruptible: true` for test jobs in GitLab CI.

**Validation output format:**
```
[CRITICAL] <finding> -- must fix before pipeline can run safely
[WARNING]  <finding> -- should fix before production
[SUGGESTION] <finding> -- improvement opportunity
```

---

## Done Criteria

A pipeline generation task is complete when:
- Validation script exits 0.
- Security check reports no CRITICAL findings.
- All jobs have explicit timeouts.
- Secrets are never hardcoded.
- Image/action versions are pinned.

A validation task is complete when:
- All three checks run (validation, security, best-practices).
- Findings are reported with severity.
- Fix recommendations are provided for each finding.

---

## Reference Files

| File | Content |
|---|---|
| `gha-best-practices.md` | Security, caching, concurrency, matrix, reusable workflows |
| `gha-actionlint-usage.md` | actionlint installation, categories, config, exit codes |
| `gha-act-usage.md` | act installation, dry-run, secrets, limitations |
| `gha-action-versions.md` | Current recommended versions, SHA pinning, Node runtime timeline |
| `gha-common-actions.md` | Catalog of actions with current SHAs and usage examples |
| `gha-common-errors.md` | Error messages and fixes for GHA |
| `gha-custom-actions.md` | Composite, Docker, JavaScript action creation |
| `gha-expressions-contexts.md` | `${{ }}` syntax, all contexts, functions, operators |
| `gha-advanced-triggers.md` | workflow_run, repository_dispatch, ChatOps, path filters |
| `gha-modern-features.md` | Job summaries, environments, container jobs, annotations |
| `gha-runners.md` | Runner labels, ARM64, GPU, macOS deprecations |
| `gha-validator-modern-features.md` | Reusable workflows, OIDC, attestations, matrix validation |
| `gitlab-ci-reference.md` | Full .gitlab-ci.yml keyword reference |
| `gitlab-best-practices.md` | Security, caching, DAG, naming, pipeline architecture |
| `gitlab-common-issues.md` | Common errors and fixes |
| `gitlab-common-patterns.md` | Ready-to-use patterns (Docker, K8s, testing, blue-green) |
| `gitlab-security-guidelines.md` | Secrets, image security, script security, supply chain |
| `gitlab-validator-best-practices.md` | Concise best practices for validator use |
| `gitlab-validator-ci-reference.md` | Reference for validation tooling |
| `azure-pipelines-reference.md` | Full Azure Pipelines YAML reference |
| `azure-yaml-schema.md` | Schema reference with deterministic generation sequence |
| `azure-tasks-reference.md` | Built-in task catalog (.NET, Node, Docker, AWS, etc.) |
| `azure-templates-guide.md` | Step/job/stage/variable templates |
| `azure-best-practices.md` | Security, performance, deployment, checklist |
| `jenkins-declarative-syntax.md` | Full declarative pipeline syntax reference |
| `jenkins-scripted-syntax.md` | Scripted pipeline syntax reference |
| `jenkins-best-practices.md` | Performance, security, structure |
| `jenkins-common-plugins.md` | Plugin reference |
| `jenkins-validator-best-practices.md` | Validation patterns |
| `jenkins-validator-plugins.md` | Plugin validation reference |
