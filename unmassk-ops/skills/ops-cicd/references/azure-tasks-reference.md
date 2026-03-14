# Azure Pipelines Tasks Reference

## Task Syntax

```yaml
- task: TaskName@MajorVersion
  displayName: Human Readable Name
  inputs:
    inputName: value
  condition: succeeded()
  continueOnError: false
  enabled: true
  timeoutInMinutes: 10
  env:
    SENSITIVE_VAR: $(secretVar)    # pass secrets via env, not inputs
```

Always pin to a known major version (`Docker@2`, not `Docker@*`). Upgrade deliberately after compatibility checks.

---

## Utility / Cache

### Cache@2

```yaml
- task: Cache@2
  displayName: Cache npm
  inputs:
    key: 'npm | "$(Agent.OS)" | package-lock.json'
    restoreKeys: |
      npm | "$(Agent.OS)"
    path: $(Pipeline.Workspace)/.npm
```

### CopyFiles@2

```yaml
- task: CopyFiles@2
  inputs:
    SourceFolder: $(Build.SourcesDirectory)
    Contents: |
      **/*.js
      !node_modules/**
    TargetFolder: $(Build.ArtifactStagingDirectory)
    CleanTargetFolder: true
```

---

## Artifacts

### PublishPipelineArtifact@1 (preferred)

```yaml
- task: PublishPipelineArtifact@1
  displayName: Publish dist
  inputs:
    targetPath: $(Build.ArtifactStagingDirectory)/dist
    artifact: webapp
    publishLocation: pipeline
```

### DownloadPipelineArtifact@2 (preferred)

```yaml
- task: DownloadPipelineArtifact@2
  inputs:
    buildType: current
    artifactName: webapp
    targetPath: $(Pipeline.Workspace)/dist
```

### PublishBuildArtifacts@1 / DownloadBuildArtifacts@1

Legacy tasks — use Pipeline variants above for new pipelines.

---

## Test Results

### PublishTestResults@2

```yaml
- task: PublishTestResults@2
  displayName: Publish test results
  condition: succeededOrFailed()
  inputs:
    testResultsFormat: JUnit
    testResultsFiles: '**/junit.xml'
    mergeTestResults: true
    failTaskOnFailedTests: true
```

### PublishCodeCoverageResults@1

```yaml
- task: PublishCodeCoverageResults@1
  inputs:
    codeCoverageTool: Cobertura
    summaryFileLocation: $(System.DefaultWorkingDirectory)/**/coverage.xml
```

---

## Node.js / JavaScript

### NodeTool@0

```yaml
- task: NodeTool@0
  displayName: Use Node.js 20
  inputs:
    versionSpec: '20.x'
```

### Npm@1

```yaml
- task: Npm@1
  displayName: npm ci
  inputs:
    command: ci

- task: Npm@1
  displayName: npm run build
  inputs:
    command: custom
    customCommand: run build
```

---

## .NET

### DotNetCoreCLI@2

```yaml
- task: DotNetCoreCLI@2
  displayName: Restore
  inputs:
    command: restore
    projects: '**/*.csproj'

- task: DotNetCoreCLI@2
  displayName: Build
  inputs:
    command: build
    projects: '**/*.csproj'
    arguments: '--configuration $(buildConfig)'

- task: DotNetCoreCLI@2
  displayName: Test
  inputs:
    command: test
    projects: '**/*Tests/*.csproj'
    arguments: '--configuration $(buildConfig) --collect:"XPlat Code Coverage"'

- task: DotNetCoreCLI@2
  displayName: Publish
  inputs:
    command: publish
    projects: '**/*.csproj'
    arguments: '--configuration $(buildConfig) --output $(Build.ArtifactStagingDirectory)'
    zipAfterPublish: true
```

### NuGetCommand@2

```yaml
- task: NuGetCommand@2
  inputs:
    command: restore
    restoreSolution: '**/*.sln'
```

---

## Python

### UsePythonVersion@0

```yaml
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.12'
    addToPath: true
```

---

## Docker

### Docker@2

```yaml
- task: Docker@2
  displayName: Docker login
  inputs:
    command: login
    containerRegistry: myDockerRegistryServiceConnection

- task: Docker@2
  displayName: Build and push
  inputs:
    command: buildAndPush
    repository: myorg/myimage
    dockerfile: Dockerfile
    containerRegistry: myDockerRegistryServiceConnection
    tags: |
      $(Build.BuildId)
      $(Build.SourceVersion)
```

---

## Kubernetes

### Kubernetes@1

```yaml
- task: Kubernetes@1
  displayName: kubectl apply
  inputs:
    connectionType: Kubernetes Service Connection
    kubernetesServiceEndpoint: myK8sConnection
    command: apply
    arguments: -f manifests/
```

### KubernetesManifest@0

```yaml
- task: KubernetesManifest@0
  displayName: Deploy manifests
  inputs:
    action: deploy
    kubernetesServiceConnection: myK8sConnection
    namespace: production
    manifests: |
      manifests/deployment.yml
      manifests/service.yml
    containers: myregistry/myimage:$(Build.BuildId)
```

### HelmDeploy@0

```yaml
- task: HelmDeploy@0
  displayName: Helm upgrade
  inputs:
    connectionType: Kubernetes Service Connection
    kubernetesServiceConnection: myK8sConnection
    namespace: production
    command: upgrade
    chartType: FilePath
    chartPath: charts/myapp
    releaseName: myapp
    arguments: --set image.tag=$(Build.BuildId) --wait --timeout 5m
```

---

## Azure

### AzureCLI@2

```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: myAzureServiceConnection
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      az webapp deploy --name $(appName) --resource-group $(rgName) --src-path dist.zip
```

### AzureWebApp@1

```yaml
- task: AzureWebApp@1
  inputs:
    azureSubscription: myAzureServiceConnection
    appType: webAppLinux
    appName: my-webapp
    package: $(Build.ArtifactStagingDirectory)/**/*.zip
```

### AzureFunctionApp@1

```yaml
- task: AzureFunctionApp@1
  inputs:
    azureSubscription: myAzureServiceConnection
    appType: functionAppLinux
    appName: my-func-app
    package: $(Build.ArtifactStagingDirectory)/**/*.zip
```

---

## Script / PowerShell

### Bash@3

```yaml
- task: Bash@3
  inputs:
    targetType: inline
    script: |
      set -e
      echo "running"
```

### PowerShell@2

```yaml
- task: PowerShell@2
  inputs:
    targetType: inline
    script: |
      Write-Host "running"
      Get-ChildItem $(Build.SourcesDirectory)
```

---

## Task Discovery

Official task reference: `https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/`

For marketplace tasks: `PublisherName.ExtensionName.TaskName@version`
