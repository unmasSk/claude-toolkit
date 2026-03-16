# GitLab CI/CD Security Guidelines

## Secrets Management

Never hardcode secrets in `.gitlab-ci.yml`. Use CI/CD variables marked as **Masked** and **Protected**.

```yaml
# wrong
deploy:
  script: deploy --token sk_live_abc123

# correct
deploy:
  script: deploy --token $DEPLOY_TOKEN
```

For secrets stored in Vault:

```yaml
deploy:
  secrets:
    DATABASE_PASSWORD:
      vault: production/db/password@ops
  script: ./deploy.sh
```

Mark variables:
- **Masked**: hidden in job logs
- **Protected**: only available on protected branches/tags
- **Expand**: disable for values containing `$` (JSON, special chars)

Exclude sensitive files from artifacts:

```yaml
build:
  artifacts:
    paths: [dist/]
    exclude:
      - "**/*.env"
      - "**/*.pem"
      - "**/*.key"
      - "**/credentials.*"
    expire_in: 1 hour
```

---

## Image Security

Pin all images to specific versions. Never use `:latest`.

```yaml
# wrong
image: node:latest

# correct — version pinned
image: node:20.14-alpine3.20

# maximum security — SHA digest
image: node@sha256:a6385a6bb2fdcb7c48fc871e35e32af8daaa82c518f934fcd0e5a42c0dd6ed71
```

For `include` from external projects, pin to SHA or protected tag — never a branch:

```yaml
include:
  - project: my-group/templates
    ref: v1.2.3      # protected tag
    file: /build.yml
```

---

## Script Security

Avoid `curl | bash`. Download, verify, then execute:

```yaml
# wrong
script: curl https://install.example.com | bash

# correct
script:
  - curl -o install.sh https://install.example.com
  - sha256sum -c install.sh.sha256
  - bash install.sh
```

Validate inputs before using them in shell:

```yaml
script:
  - |
    if [[ ! "$DEPLOY_ENV" =~ ^(staging|production)$ ]]; then
      echo "Invalid DEPLOY_ENV: $DEPLOY_ENV"
      exit 1
    fi
    ./deploy.sh "$DEPLOY_ENV"
```

Use `set -e` and `set -o pipefail` for error handling. Never echo secret variables to logs.

Do not set `CI_DEBUG_TRACE: "true"` on production jobs — it exposes all variable values in logs.

---

## Access Control

Protected branches prevent unapproved code from reaching production runners. Configure in Settings > Repository > Protected Branches.

Protected environments require approval before deployment. Configure in Settings > CI/CD > Environments.

Runner tags restrict which runners execute sensitive jobs:

```yaml
deploy-production:
  tags:
    - production-runner
    - secured
  script: ./deploy.sh
```

`resource_group` prevents concurrent deployments:

```yaml
deploy-production:
  resource_group: production
  when: manual
```

---

## Supply Chain Security

Use lock files and reproducible installs:

```yaml
# npm
script: npm ci

# pip
script: pip install -r requirements.txt --require-hashes

# go
script: go mod verify && go build
```

Enable built-in security templates:

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml
```

SBOM generation:

```yaml
sbom:
  image: anchore/syft:latest
  script: syft packages dir:. -o cyclonedx-json > sbom.json
  artifacts:
    paths: [sbom.json]
    expire_in: 1 year
```

---

## Audit Trail

Log deployment context in `before_script`:

```yaml
deploy:
  before_script:
    - echo "Deploy by $GITLAB_USER_LOGIN at $(date -u)"
    - echo "Commit $CI_COMMIT_SHORT_SHA on $CI_COMMIT_BRANCH"
  script: ./deploy.sh
```

---

## Security Checklist

| Category | Check |
|---|---|
| Secrets | No hardcoded values in YAML |
| Secrets | Sensitive variables masked + protected |
| Secrets | Secrets scoped to target environment |
| Images | All images version-pinned (no `:latest`) |
| Images | Container vulnerability scanning enabled |
| Scripts | No `curl \| bash` patterns |
| Scripts | Inputs validated before shell use |
| Scripts | `set -e` in multi-step scripts |
| Artifacts | Specific paths, sensitive files excluded |
| Artifacts | `expire_in` set on all artifact blocks |
| Access | Protected branches for main/production |
| Access | Protected environments for production |
| Access | `resource_group` on all deploy jobs |
| Access | Specific runner tags for sensitive jobs |
| Supply chain | Lock files committed and used (`npm ci`, not `npm install`) |
| Supply chain | Dependency and secret scanning enabled |

---

## Incident Response — Exposed Secret

1. Rotate the compromised credential immediately.
2. Check pipeline logs and audit events for unauthorized use.
3. Remove the secret from git history (`git filter-repo` or GitLab secret push protection).
4. Enable secret detection scanning if not already active.
5. Document scope and timeline for the security team.
