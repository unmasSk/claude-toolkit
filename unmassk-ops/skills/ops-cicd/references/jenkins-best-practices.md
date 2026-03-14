# Jenkins Pipeline Best Practices

## Performance

### Combine shell commands

Each `sh` step has startup overhead. Combine into multi-line scripts.

```groovy
// wrong
sh 'mkdir build'
sh 'cd build && cmake ..'
sh 'make'

// correct
sh '''
    mkdir build
    cd build && cmake ..
    make
'''
```

### Run heavy operations on agents, not the controller

The controller is shared across all builds. Heavy computation and file reads should run on agents.

```groovy
// wrong — loads file into controller memory
def content = readFile('huge-log.txt')
def lines = content.split('\n')

// correct — runs on agent
def errorCount = sh(script: 'grep ERROR huge-log.txt | wc -l', returnStdout: true).trim()
```

### Minimize `returnStdout` output size

`sh(returnStdout: true)` transfers output to the controller. Keep it small — use `trim()`, pipe through `jq`, or extract only the field you need.

---

## Security

### Never hardcode credentials

```groovy
// wrong
sh 'docker login -u admin -p password123'

// correct
withCredentials([usernamePassword(
    credentialsId: 'docker-hub',
    usernameVariable: 'DOCKER_USER',
    passwordVariable: 'DOCKER_PASS'
)]) {
    sh 'docker login -u $DOCKER_USER -p $DOCKER_PASS'
}
```

### Validate string parameters before interpolation

```groovy
// wrong — injection risk
sh "git checkout ${params.BRANCH}"

// correct — use choice parameter or validate
if (!params.BRANCH.matches(/^[a-zA-Z0-9_\-\/]+$/)) {
    error "Invalid branch name: ${params.BRANCH}"
}
sh "git checkout ${params.BRANCH}"
```

### Pin image versions

Never use `latest` or `lts` tags in agents. Use specific versions.

```groovy
// wrong
agent { docker { image 'node:latest' } }

// correct
agent { docker { image 'node:22.11.0-bookworm-slim' } }
```

Node.js Alpine images are marked experimental by the Node.js project — prefer `-bookworm-slim`. Java: use Eclipse Temurin (`maven:3.9.11-eclipse-temurin-21`). Go: Alpine works (statically compiled).

---

## Reliability

### Set pipeline and stage timeouts

```groovy
// pipeline level
options {
    timeout(time: 1, unit: 'HOURS')
}

// stage level
stage('Integration Test') {
    options { timeout(time: 30, unit: 'MINUTES') }
    steps { sh './test-integration.sh' }
}

// scripted
timeout(time: 30, unit: 'MINUTES') {
    node { sh './test-integration.sh' }
}
```

### Use `catchError` to control build result without aborting

```groovy
// mark build unstable if integration tests fail, but continue
catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
    sh 'npm run test:integration'
}

// warn only — build stays green
warnError('Linting warnings detected') {
    sh 'npm run lint'
}
```

`catchError` parameters:

| Parameter | Values |
|---|---|
| `buildResult` | SUCCESS, UNSTABLE, FAILURE, NOT_BUILT, ABORTED |
| `stageResult` | SUCCESS, UNSTABLE, FAILURE, NOT_BUILT, ABORTED |
| `catchInterruptions` | true (default) / false |

### Always clean the workspace

```groovy
post {
    always { cleanWs() }
}

// scripted — in finally
} finally {
    cleanWs()
}
```

### Retry flaky operations

```groovy
retry(3) {
    sh 'curl -f https://flaky-api.example.com/data'
}
```

---

## Recommended `options` block

```groovy
options {
    buildDiscarder(logRotator(
        numToKeepStr: '10',
        daysToKeepStr: '30',
        artifactNumToKeepStr: '5'
    ))
    timestamps()
    timeout(time: 1, unit: 'HOURS')
    disableConcurrentBuilds()
}
```

---

## Pipeline structure

### Use parallel for independent work

```groovy
stage('Test') {
    failFast true
    parallel {
        stage('Unit')        { steps { sh 'make test:unit' } }
        stage('Integration') { steps { sh 'make test:integration' } }
    }
}
```

### Use `input` outside `steps {}` to free agents during approval

```groovy
// correct — agent released while waiting
stage('Approval') {
    input {
        message 'Deploy to production?'
        ok 'Deploy'
        submitter 'admin,ops'
    }
    steps { sh './deploy.sh' }
}

// wrong — agent held during the entire wait
stage('Approval') {
    steps {
        input 'Deploy to production?'
        sh './deploy.sh'
    }
}
```

### Use webhooks instead of `pollSCM`

`pollSCM` polls on a schedule — wasteful and slow. Configure repository webhooks for immediate triggers. Use `pollSCM` only as a fallback.

### Use shared libraries for repeated logic

```groovy
@Library('my-shared-library@v2.1.0') _

pipeline {
    stages {
        stage('Build') { steps { buildMavenProject() } }
        stage('Deploy') { steps { deployToKubernetes(env: params.ENVIRONMENT) } }
    }
}
```

---

## Test results

Publish test results unconditionally, even when tests fail.

```groovy
post {
    always {
        junit '**/target/surefire-reports/*.xml'
    }
    success {
        archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
    }
}
```

---

## Kubernetes agent best practices

Always set resource requests and limits. Use a dedicated service account.

```groovy
agent {
    kubernetes {
        yaml '''
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  containers:
  - name: build
    image: maven:3.9.11-eclipse-temurin-21
    command: [cat]
    tty: true
    resources:
      requests: { memory: 1Gi, cpu: 500m }
      limits:   { memory: 2Gi, cpu: 1000m }
'''
    }
}
```

---

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Hardcoded credentials | `withCredentials` or `environment { VAR = credentials(...) }` |
| `image 'node:latest'` | Pin to specific version + variant |
| `sh` inside a `@NonCPS` method | `@NonCPS` cannot call pipeline steps |
| `input` inside `steps {}` | Move `input` to declarative `input {}` block or outside node block |
| `readFile` on large files | Run processing on agent with `sh(returnStdout: true)` |
| No timeout | Add `timeout` in `options` and on slow stages |
| No `cleanWs()` | Add in `post { always }` or scripted `finally` |
| `pollSCM` as primary trigger | Use webhooks; fallback to `pollSCM` |
