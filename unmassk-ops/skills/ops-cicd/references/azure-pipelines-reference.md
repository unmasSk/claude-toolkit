# Azure Pipelines YAML Reference

## Pipeline Hierarchy

```
Pipeline → Stages → Jobs → Steps
```

Three valid pipeline structures: `stages`-based (most complete), `jobs`-based (no stages), `steps`-only (single job).

---

## Root Keywords

```yaml
trigger:
  branches:
    include: [main, release/*]
    exclude: [feature/*]
  paths:
    include: [src/**]
    exclude: [docs/**]
  tags:
    include: [v*]

pr:
  branches:
    include: [main]

schedules:
- cron: "0 2 * * 1-5"
  displayName: Nightly weekday build
  branches:
    include: [main]
  always: true

pool:
  vmImage: ubuntu-22.04     # Microsoft-hosted
  # name: MyPool            # self-hosted pool

variables:
- group: my-variable-group
- name: buildConfig
  value: Release

parameters:
- name: environment
  type: string
  default: staging
  values: [dev, staging, production]

resources:
  repositories:
  - repository: templates
    type: git
    name: MyProject/Templates
    ref: refs/tags/v1.2.0
  pipelines:
  - pipeline: upstream
    source: UpstreamPipeline
    trigger:
      branches: [main]
  containers:
  - container: node
    image: node:20-alpine
```

---

## Stages

```yaml
stages:
- stage: Build
  displayName: Build Stage
  dependsOn: []          # no dependency — runs immediately
  condition: succeeded()
  variables:
    stageVar: value
  jobs:
  - job: ...

- stage: Deploy
  displayName: Deploy Stage
  dependsOn:
  - Build
  - SecurityScan
  condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
  jobs:
  - deployment: ...
```

---

## Jobs

### Regular job

```yaml
jobs:
- job: BuildApp
  displayName: Build Application
  pool:
    vmImage: ubuntu-22.04
  timeoutInMinutes: 30
  cancelTimeoutInMinutes: 5
  dependsOn: []
  condition: succeeded()
  continueOnError: false
  variables:
    jobVar: value
  strategy:
    matrix:
      Node18:
        nodeVersion: '18'
      Node20:
        nodeVersion: '20'
    maxParallel: 2
  steps:
  - ...
```

### Deployment job

```yaml
jobs:
- deployment: DeployProd
  displayName: Deploy to Production
  environment:
    name: production
    resourceName: web-app
  strategy:
    runOnce:
      preDeploy:
        steps:
        - script: ./pre-checks.sh
      deploy:
        steps:
        - script: ./deploy.sh
      routeTraffic:
        steps:
        - script: ./route-traffic.sh
      postRouteTraffic:
        steps:
        - script: ./smoke-test.sh
      on:
        failure:
          steps:
          - script: ./rollback.sh
        success:
          steps:
          - script: ./notify.sh
```

Deployment strategies: `runOnce`, `rolling` (maxParallel), `canary` (increments: [10, 25, 50]).

---

## Steps

```yaml
steps:
- checkout: self
  clean: true
  fetchDepth: 1
  persistCredentials: false

- script: npm run build
  displayName: Build
  workingDirectory: $(Build.SourcesDirectory)
  failOnStderr: false
  env:
    MY_SECRET: $(secretVar)

- bash: |
    set -e
    npm ci
    npm test
  displayName: Test

- pwsh: Write-Host "PowerShell Core"

- task: TaskName@2
  displayName: Task Name
  inputs:
    key: value
  condition: succeeded()
  continueOnError: false
  timeoutInMinutes: 10
  env:
    SENSITIVE: $(secretVar)

- publish: $(Build.ArtifactStagingDirectory)
  artifact: drop

- download: current
  artifact: drop
  patterns: '**/*.zip'

- template: templates/build-steps.yml
  parameters:
    nodeVersion: '20'
```

---

## Conditions

```yaml
condition: succeeded()          # default
condition: failed()
condition: succeededOrFailed()
condition: always()
condition: canceled()

# Custom
condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')
condition: and(succeeded(), startsWith(variables['Build.SourceBranch'], 'refs/heads/release/'))
condition: or(eq(variables['Build.Reason'], 'PullRequest'), eq(variables['Build.Reason'], 'Manual'))
condition: not(eq(variables['Skip'], 'true'))
```

---

## Variable Syntax

```yaml
$(variableName)              # macro — queue time
${{ variables.name }}        # template expression — compile time
$[variables.name]            # runtime expression

# Predefined
$(Build.BuildId)
$(Build.SourceBranch)        # refs/heads/main
$(Build.SourceVersion)       # commit SHA
$(Build.ArtifactStagingDirectory)
$(Build.SourcesDirectory)
$(Agent.OS)
$(Pipeline.Workspace)
$(System.StageName)
$(System.JobName)
```

Cross-job output variables:

```yaml
# Set output in a step
- script: echo "##vso[task.setvariable variable=myVar;isOutput=true]value"
  name: setVarStep

# Read in same stage
$[ dependencies.JobName.outputs['setVarStep.myVar'] ]

# Read across stages
$[ stageDependencies.StageName.JobName.outputs['setVarStep.myVar'] ]
```

---

## Container Jobs and Service Containers

```yaml
resources:
  containers:
  - container: nodeImage
    image: node:20-alpine
  - container: pgService
    image: postgres:16
    env:
      POSTGRES_PASSWORD: ci
    ports:
    - 5432:5432

jobs:
- job: Test
  container: nodeImage
  services:
    postgres: pgService
  steps:
  - script: npm test
    env:
      DATABASE_URL: postgres://postgres:ci@postgres:5432/test
```

---

## Deployment Environments

Environments track deployment history and enforce approval gates configured in Azure DevOps (Settings > Environments — not in YAML). Using a `deployment` job with `environment:` activates this tracking.

```yaml
- deployment: Deploy
  environment:
    name: production
    resourceName: myapp      # specific VM or k8s namespace
  strategy:
    runOnce:
      deploy:
        steps:
        - script: ./deploy.sh
```

---

## Templates (quick reference)

```yaml
# Include
- template: templates/build-steps.yml
  parameters:
    nodeVersion: '20'

# Extends (security policy enforcement)
extends:
  template: templates/secure-pipeline.yml
  parameters:
    buildSteps:
    - script: npm run build
```

Template types: `steps`, `jobs`, `stages`, `variables`. See `azure-templates-guide.md` for full coverage.
