# Azure Pipelines Best Practices

## Security

### Never hardcode secrets

```yaml
# wrong
variables:
  API_KEY: sk-1234567890abcdef

# correct — from variable group or pipeline secret
variables:
- group: prod-secrets
- name: buildConfig
  value: Release
```

Store credentials in service connections. Reference them from tasks — never store in YAML.

### Pin VM images and task versions

```yaml
# wrong
pool:
  vmImage: ubuntu-latest

- task: Docker@2   # ok but prefer known-working major
```

```yaml
# correct
pool:
  vmImage: ubuntu-22.04

- task: Docker@2
  inputs:
    containerRegistry: myDockerRegistryServiceConnection
```

`ubuntu-latest` changes on Microsoft's schedule. `ubuntu-22.04` is stable.

### Mark sensitive variables as secret

In the Azure DevOps UI (not YAML): Pipeline Variables → lock icon. Secret variables are masked in logs and not passed to forked PR builds.

---

## Performance

### Cache dependencies

```yaml
- task: Cache@2
  displayName: Cache npm
  inputs:
    key: 'npm | "$(Agent.OS)" | package-lock.json'
    restoreKeys: |
      npm | "$(Agent.OS)"
    path: $(Pipeline.Workspace)/.npm

- script: npm ci --cache $(Pipeline.Workspace)/.npm
  displayName: Install dependencies
```

### Shallow clone

```yaml
- checkout: self
  fetchDepth: 1
  clean: true
```

### Parallel jobs

Run independent jobs simultaneously using `dependsOn: []`:

```yaml
stages:
- stage: Test
  dependsOn: Build
  jobs:
  - job: UnitTest
    dependsOn: []
    steps: [...]
  - job: IntegrationTest
    dependsOn: []
    steps: [...]

- stage: Deploy
  dependsOn:
  - Test
```

### Matrix for cross-version testing

```yaml
strategy:
  matrix:
    Node18:
      nodeVersion: '18'
    Node20:
      nodeVersion: '20'
    Node22:
      nodeVersion: '22'
  maxParallel: 3
```

---

## Reliability

### Set timeouts on every job

```yaml
jobs:
- job: Build
  timeoutInMinutes: 30
  cancelTimeoutInMinutes: 5
```

Default is 60 minutes. Jobs that hang (network issues, test deadlocks) must not consume agents indefinitely.

### Use conditions to control flow

```yaml
# Always cleanup
- script: ./cleanup.sh
  condition: always()

# Only notify on failure
- script: ./notify.sh
  condition: failed()

# Gate deploy on branch + success
- stage: Deploy
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
```

### Publish test results — always

```yaml
- task: PublishTestResults@2
  condition: succeededOrFailed()
  inputs:
    testResultsFormat: JUnit
    testResultsFiles: '**/junit.xml'
    failTaskOnFailedTests: true
```

Without `succeededOrFailed()`, results are lost when tests fail.

---

## Deployment

### Use deployment jobs for environments

```yaml
- deployment: DeployProduction
  displayName: Deploy to Production
  environment: production
  strategy:
    runOnce:
      deploy:
        steps:
        - script: ./deploy.sh
      on:
        failure:
          steps:
          - script: ./rollback.sh
```

`deployment` jobs provide deployment history, environment protection, and approval gates (configured in Azure DevOps Environments UI).

### Gate production deploys

Configure required approvers in Azure DevOps > Environments > production > Approvals and checks. This is enforced at runtime, not in YAML.

### Canary deployments

```yaml
strategy:
  canary:
    increments: [10, 25, 50, 100]
    deploy:
      steps:
      - script: deploy.sh --canary $(strategy.canary.increment)
    postDeploy:
      steps:
      - script: ./validate.sh
```

---

## Maintainability

### `displayName` on every stage, job, and non-trivial step

```yaml
- stage: Build
  displayName: Build and Unit Test
  jobs:
  - job: BuildApp
    displayName: Compile and Package
    steps:
    - script: npm run build
      displayName: Build with npm
```

### Use templates for repeated logic

```yaml
# templates/npm-ci.yml
parameters:
- name: nodeVersion
  type: string
  default: '20'

steps:
- task: NodeTool@0
  inputs:
    versionSpec: ${{ parameters.nodeVersion }}
- task: Cache@2
  inputs:
    key: 'npm | "$(Agent.OS)" | package-lock.json'
    path: $(Pipeline.Workspace)/.npm
- script: npm ci --cache $(Pipeline.Workspace)/.npm
```

See `azure-templates-guide.md` for all template types.

### Trigger and path filters

```yaml
trigger:
  branches:
    include: [main, release/*]
  paths:
    exclude: [docs/**, '*.md']

pr:
  branches:
    include: [main]
  paths:
    include: [src/**]
```

---

## Anti-Patterns

| Anti-pattern | Fix |
|---|---|
| `vmImage: ubuntu-latest` | Pin to `ubuntu-22.04` |
| Secrets in YAML `variables:` | Use variable groups or pipeline secrets |
| No `timeoutInMinutes` | Set on every job |
| `continueOnError: true` on security/build steps | Only for non-critical steps (lint, optional scans) |
| `PublishTestResults` without `succeededOrFailed()` | Always add the condition |
| Regular `job:` for deployments | Use `deployment:` with `environment:` |
| Templates from branch `ref: main` | Pin to SHA or semver tag |
| No `displayName` | Add to all stages, jobs, and non-trivial steps |
