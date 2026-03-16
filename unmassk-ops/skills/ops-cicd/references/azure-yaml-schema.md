# Azure Pipelines YAML Schema

## Pipeline Structures

Three valid structures — pick based on complexity:

```yaml
# 1. steps-only (single job, no stages)
pool:
  vmImage: ubuntu-22.04
steps:
- script: echo "simple"

# 2. jobs-based (multiple jobs, no stages)
jobs:
- job: Job1
  steps: [...]
- job: Job2
  steps: [...]

# 3. stages-based (full hierarchy)
stages:
- stage: Build
  jobs:
  - job: BuildJob
    steps: [...]
```

Do not mix levels — e.g., `stages:` and `jobs:` cannot both appear as root siblings.

---

## Stage Schema

```yaml
stages:
- stage: string               # identifier (no spaces)
  displayName: string         # UI label
  dependsOn:                  # list of stage identifiers or []
  - StageName
  condition: string           # expression
  variables:                  # stage-scoped
    key: value
  jobs:
  - ...
```

---

## Job Schema

```yaml
jobs:
- job: string
  displayName: string
  dependsOn:                  # job identifiers within same stage
  - JobName
  condition: string
  timeoutInMinutes: number    # default: 60
  cancelTimeoutInMinutes: number
  continueOnError: boolean
  pool:
    vmImage: string
    # OR
    name: string
    demands:
    - capability -equals value
  container: containerAlias
  services:
    alias: containerAlias
  variables:
    key: value
  strategy:
    matrix:
      MatrixName:
        variable: value
    maxParallel: number
  steps:
  - ...
```

---

## Deployment Job Schema

```yaml
jobs:
- deployment: string
  displayName: string
  pool:
    vmImage: string
  environment:
    name: string
    resourceName: string
    resourceType: string      # Kubernetes, VirtualMachine
  strategy:
    runOnce | rolling | canary: ...
```

### Deployment strategy shapes

```yaml
# runOnce
strategy:
  runOnce:
    preDeploy:
      steps: [...]
    deploy:
      steps: [...]
    routeTraffic:
      steps: [...]
    postRouteTraffic:
      steps: [...]
    on:
      failure:
        steps: [...]
      success:
        steps: [...]

# rolling
strategy:
  rolling:
    maxParallel: 2
    preDeploy:
      steps: [...]
    deploy:
      steps: [...]

# canary
strategy:
  canary:
    increments: [10, 25, 50]
    preDeploy:
      steps: [...]
    deploy:
      steps: [...]
    postDeploy:
      steps: [...]
```

---

## Step Schema

```yaml
# script (sh on Linux/macOS, cmd on Windows)
- script: string | multiline
  displayName: string
  workingDirectory: string
  failOnStderr: boolean
  condition: string
  continueOnError: boolean
  env:
    VAR: value

# bash (cross-platform bash)
- bash: string | multiline

# pwsh (PowerShell Core, cross-platform)
- pwsh: string | multiline

# powershell (Windows PowerShell only)
- powershell: string | multiline

# task
- task: Name@version
  displayName: string
  inputs:
    key: value
  condition: string
  continueOnError: boolean
  enabled: boolean
  timeoutInMinutes: number
  env:
    KEY: $(secretVar)

# checkout
- checkout: self | none | repositoryAlias
  clean: boolean
  fetchDepth: number
  lfs: boolean
  submodules: boolean | recursive
  persistCredentials: boolean

# download
- download: current | pipelineAlias
  artifact: string
  patterns: string

# publish (shorthand for PublishPipelineArtifact)
- publish: path
  artifact: string

# template
- template: path/to/steps.yml
  parameters:
    key: value
```

---

## Conditions Reference

```yaml
# Functions
succeeded()           # previous tasks succeeded (default)
failed()
succeededOrFailed()   # any completion
always()
canceled()

# Comparison
eq(a, b)
ne(a, b)
lt(a, b)
gt(a, b)
contains(string, substring)
startsWith(string, prefix)
endsWith(string, suffix)
in(search, value1, value2)
containsValue(array, value)

# Logical
and(expr1, expr2)
or(expr1, expr2)
not(expr)

# Examples
condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
condition: or(eq(variables['Build.Reason'], 'PullRequest'), eq(variables['Build.Reason'], 'Schedule'))
condition: not(startsWith(variables['Build.SourceBranch'], 'refs/heads/feature/'))
```

---

## Variable Expression Syntax

```yaml
$(varName)                    # macro — resolved at queue time
${{ variables.varName }}      # template expression — compile time
$[variables.varName]          # runtime expression
```

Cross-job output:

```yaml
# Producer (in step named "setVar")
- script: echo "##vso[task.setvariable variable=myVar;isOutput=true]hello"
  name: setVar

# Consumer — same stage
$[ dependencies.ProducerJob.outputs['setVar.myVar'] ]

# Consumer — different stage
$[ stageDependencies.ProducerStage.ProducerJob.outputs['setVar.myVar'] ]
```

---

## Resources Schema

```yaml
resources:
  repositories:
  - repository: alias
    type: github | git | bitbucket
    name: org/repo
    ref: refs/tags/v1.0.0    # always pin

  pipelines:
  - pipeline: alias
    source: PipelineName
    trigger:
      branches: [main]

  containers:
  - container: alias
    image: image:tag
    env:
      KEY: value
    ports:
    - 5432:5432

  packages:
  - package: alias
    type: npm | nuget
    connection: serviceConnectionName
    name: package-name
    version: '1.0.0'
```

---

## Schema Validation

- VS Code extension: Azure Pipelines (Microsoft) — provides IntelliSense and inline validation.
- Official JSON schema: `https://raw.githubusercontent.com/microsoft/azure-pipelines-vscode/main/service-schema.json`
- Official YAML schema reference: `https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/`
