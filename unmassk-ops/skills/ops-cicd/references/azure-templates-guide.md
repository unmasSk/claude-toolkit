# Azure Pipelines Templates Guide

## Template Types

| Type | Reuses | File content starts with |
|---|---|---|
| Step template | A list of steps | `steps:` |
| Job template | One or more jobs | `jobs:` |
| Stage template | One or more stages | `stages:` |
| Variable template | Variables block | `variables:` |

---

## Step Template

```yaml
# templates/npm-ci.yml
parameters:
- name: nodeVersion
  type: string
  default: '20'
- name: workingDirectory
  type: string
  default: '.'

steps:
- task: NodeTool@0
  inputs:
    versionSpec: ${{ parameters.nodeVersion }}
- task: Cache@2
  inputs:
    key: 'npm | "$(Agent.OS)" | ${{ parameters.workingDirectory }}/package-lock.json'
    path: $(Pipeline.Workspace)/.npm
- script: npm ci --cache $(Pipeline.Workspace)/.npm
  workingDirectory: ${{ parameters.workingDirectory }}
  displayName: Install dependencies
- script: npm run build
  workingDirectory: ${{ parameters.workingDirectory }}
  displayName: Build
```

```yaml
# usage
jobs:
- job: Build
  steps:
  - checkout: self
    fetchDepth: 1
  - template: templates/npm-ci.yml
    parameters:
      nodeVersion: '20'
```

---

## Job Template

```yaml
# templates/test-job.yml
parameters:
- name: nodeVersion
  type: string
  default: '20'
- name: osImage
  type: string
  default: ubuntu-22.04

jobs:
- job: Test_${{ replace(parameters.nodeVersion, '.', '_') }}
  displayName: Test on Node ${{ parameters.nodeVersion }}
  pool:
    vmImage: ${{ parameters.osImage }}
  timeoutInMinutes: 30
  steps:
  - task: NodeTool@0
    inputs:
      versionSpec: ${{ parameters.nodeVersion }}
  - script: npm ci
  - script: npm test
  - task: PublishTestResults@2
    condition: succeededOrFailed()
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: '**/junit.xml'
```

```yaml
# usage
stages:
- stage: Test
  jobs:
  - template: templates/test-job.yml
    parameters:
      nodeVersion: '18'
  - template: templates/test-job.yml
    parameters:
      nodeVersion: '20'
  - template: templates/test-job.yml
    parameters:
      nodeVersion: '22'
```

---

## Stage Template

```yaml
# templates/deploy-stage.yml
parameters:
- name: environment
  type: string
- name: serviceConnection
  type: string
- name: dependsOn
  type: object
  default: []

stages:
- stage: Deploy_${{ parameters.environment }}
  displayName: Deploy to ${{ parameters.environment }}
  ${{ if gt(length(parameters.dependsOn), 0) }}:
    dependsOn: ${{ parameters.dependsOn }}
  jobs:
  - deployment: Deploy
    environment: ${{ parameters.environment }}
    strategy:
      runOnce:
        deploy:
          steps:
          - task: AzureWebApp@1
            inputs:
              azureSubscription: ${{ parameters.serviceConnection }}
              appName: myapp-${{ parameters.environment }}
              package: $(Pipeline.Workspace)/drop/**/*.zip
        on:
          failure:
            steps:
            - script: echo "Deploy to ${{ parameters.environment }} failed"
```

```yaml
# usage
stages:
- stage: Build
  jobs: [...]

- template: templates/deploy-stage.yml
  parameters:
    environment: staging
    serviceConnection: AzureStaging

- template: templates/deploy-stage.yml
  parameters:
    environment: production
    serviceConnection: AzureProduction
    dependsOn: [Deploy_staging]
```

---

## Variable Template

```yaml
# templates/variables-common.yml
variables:
  nodeVersion: '20'
  buildConfig: Release
  artifactName: drop
```

```yaml
# usage
variables:
- template: templates/variables-common.yml
- name: extraVar
  value: customValue
```

---

## Template Parameters

```yaml
parameters:
- name: env
  type: string
  values: [dev, staging, production]  # constrained enumeration

- name: runTests
  type: boolean
  default: true

- name: timeout
  type: number
  default: 30

- name: regions
  type: object
  default: [westus, eastus]

- name: extraSteps
  type: stepList
  default: []

- name: extraJobs
  type: jobList
  default: []
```

---

## Template Expressions

Compile-time only (`${{ }}`).

```yaml
# Conditional block
- ${{ if eq(parameters.runTests, true) }}:
  - script: npm test
    displayName: Run tests

# Negation
- ${{ if ne(parameters.env, 'production') }}:
  - script: echo "Not production"

# Iteration over list
- ${{ each region in parameters.regions }}:
  - script: deploy.sh ${{ region }}
    displayName: Deploy to ${{ region }}

# Iteration over map
- ${{ each item in parameters.envMap }}:
  - stage: Deploy_${{ item.key }}
    variables:
      targetUrl: ${{ item.value.url }}
```

---

## Extends (security enforcement)

`extends` locks the pipeline structure. The base template controls what steps are allowed.

```yaml
# templates/secure-pipeline.yml
parameters:
- name: buildSteps
  type: stepList
  default: []

stages:
- stage: Build
  jobs:
  - job: Build
    steps:
    - script: echo "Mandatory security scan"
    - ${{ each step in parameters.buildSteps }}:
      - ${{ step }}
```

```yaml
# azure-pipelines.yml
extends:
  template: templates/secure-pipeline.yml
  parameters:
    buildSteps:
    - script: npm ci
    - script: npm run build
```

---

## Cross-Repository Templates

```yaml
resources:
  repositories:
  - repository: central-templates
    type: git
    name: MyOrg/pipeline-templates
    ref: refs/tags/v2.1.0    # pin to tag, not branch

stages:
- template: stages/deploy.yml@central-templates
  parameters:
    environment: production
```

---

## Directory Layout

```
templates/
├── steps/
│   ├── npm-ci.yml
│   ├── docker-build.yml
│   └── security-scan.yml
├── jobs/
│   ├── test-matrix.yml
│   └── build-job.yml
├── stages/
│   ├── deploy-stage.yml
│   └── release-stage.yml
└── variables/
    ├── common.yml
    └── environments.yml
```

---

## Rules

- Parameters must be explicitly typed with defaults where optional.
- Use `values:` to constrain string parameters that should be an enumeration.
- Cross-repo template refs must pin to a tag or commit SHA — never a mutable branch.
- Prefer `template:` inclusion over copy-pasting YAML blocks. If you copy, you own both copies.
- Environment approval gates are enforced in Azure DevOps Environments UI, not by boolean template parameters.
