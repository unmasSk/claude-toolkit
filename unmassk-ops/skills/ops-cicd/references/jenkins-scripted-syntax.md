# Jenkins Scripted Pipeline Syntax

## Skeleton

```groovy
properties([
    buildDiscarder(logRotator(numToKeepStr: '10')),
    disableConcurrentBuilds(),
    parameters([
        choice(name: 'ENVIRONMENT', choices: ['dev', 'staging', 'production'], description: '')
    ])
])

def version

timestamps {
    node('linux') {
        try {
            stage('Checkout') {
                checkout scm
                version = sh(script: 'git describe --tags --always', returnStdout: true).trim()
                currentBuild.displayName = "#${env.BUILD_NUMBER} - ${version}"
            }

            stage('Build') {
                sh 'make build'
            }

            stage('Test') {
                sh 'make test'
                junit '**/test-results/*.xml'
            }

            stage('Deploy') {
                if (params.ENVIRONMENT == 'production') {
                    timeout(time: 30, unit: 'MINUTES') {
                        input message: 'Deploy to production?', submitter: 'admin,ops'
                    }
                }
                sh "deploy.sh ${params.ENVIRONMENT}"
            }

            currentBuild.result = 'SUCCESS'

        } catch (Exception e) {
            currentBuild.result = 'FAILURE'
            throw e
        } finally {
            cleanWs()
        }
    }
}
```

---

## node

```groovy
node { }                     // any available executor
node('linux') { }            // labeled node
node('linux && java21') { }  // label expression
```

---

## stages

Stage blocks are for visualization only — they do not allocate executors.

```groovy
node {
    stage('Build') { sh 'make build' }
    stage('Test')  { sh 'make test' }
}
```

---

## parallel

```groovy
node {
    stage('Tests') {
        parallel(
            'Unit': {
                node('linux') { sh 'make test:unit' }
            },
            'Integration': {
                node('linux') { sh 'make test:integration' }
            }
        )
    }
}
```

Dynamic parallel with captured loop variable:

```groovy
def branches = [:]
def envs = ['dev', 'qa', 'staging']

for (int i = 0; i < envs.size(); i++) {
    def e = envs[i]    // capture — closure captures reference, not value
    branches["Deploy ${e}"] = {
        node { sh "deploy.sh ${e}" }
    }
}

parallel branches
```

failFast:

```groovy
parallel(
    failFast: true,
    'Region A': { node { sh 'deploy.sh us-east' } },
    'Region B': { node { sh 'deploy.sh eu-west' } }
)
```

---

## Error handling

```groovy
node {
    try {
        sh 'make build'
    } catch (hudson.AbortException e) {
        echo "Aborted: ${e.message}"
    } catch (Exception e) {
        currentBuild.result = 'FAILURE'
        throw e
    } finally {
        cleanWs()
    }
}
```

---

## withCredentials

```groovy
withCredentials([
    usernamePassword(credentialsId: 'docker-hub', usernameVariable: 'USER', passwordVariable: 'PASS'),
    string(credentialsId: 'api-token', variable: 'TOKEN'),
    sshUserPrivateKey(credentialsId: 'ssh-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
    file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')
]) {
    sh 'docker login -u $USER -p $PASS'
}
```

---

## withEnv / env

```groovy
withEnv(['MY_VAR=value', 'ANOTHER=foo']) {
    sh 'echo $MY_VAR'
}

// Direct assignment — persists for duration of node block
env.BUILD_TAG = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"

// Capture from shell
env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
```

---

## Docker (docker-workflow plugin)

```groovy
node {
    // Run inside image
    docker.image('maven:3.9.11-eclipse-temurin-21').inside('-v $HOME/.m2:/root/.m2') {
        sh 'mvn clean package'
    }

    // Build
    def img = docker.build("myapp:${env.BUILD_NUMBER}")

    // Push
    docker.withRegistry('https://registry.example.com', 'registry-creds') {
        img.push()
        img.push('latest')
    }

    // Sidecar
    docker.image('postgres:16').withRun('-e POSTGRES_PASSWORD=test') { db ->
        docker.image('maven:3.9.11').inside("--link ${db.id}:postgres") {
            sh 'mvn verify'
        }
    }
}
```

---

## Shared library

```groovy
@Library('my-shared-library@v2.1.0') _

node {
    buildMavenProject()
    deployToKubernetes(env: params.ENVIRONMENT)
}
```

---

## @NonCPS

Use for complex Groovy logic that must not use pipeline continuations (serialization boundary).

```groovy
@NonCPS
def parseJson(String text) {
    new groovy.json.JsonSlurper().parseText(text)
}

// IMPORTANT: Cannot call pipeline steps (sh, echo, etc.) inside @NonCPS methods
```

---

## Built-in variables

```groovy
env.BUILD_NUMBER
env.JOB_NAME
env.BRANCH_NAME      // multibranch only
env.GIT_COMMIT
env.WORKSPACE

currentBuild.result           // SUCCESS, FAILURE, UNSTABLE, ABORTED, null
currentBuild.currentResult
currentBuild.number
currentBuild.displayName
currentBuild.description
currentBuild.previousBuild    // null if first build

params.PARAM_NAME
```

---

## properties (pipeline configuration)

```groovy
properties([
    buildDiscarder(logRotator(numToKeepStr: '10', daysToKeepStr: '30')),
    disableConcurrentBuilds(),
    parameters([
        string(name: 'DEPLOY_ENV', defaultValue: 'staging', description: ''),
        choice(name: 'VERSION', choices: ['1.0', '1.1', '2.0'], description: ''),
        booleanParam(name: 'RUN_TESTS', defaultValue: true, description: '')
    ]),
    pipelineTriggers([
        cron('H 2 * * 1-5')
    ])
])
```

---

## input (approval gate)

Call `input` outside a `node` block to release the executor while waiting.

```groovy
stage('Approval') {
    // no node here — agent is released
    timeout(time: 1, unit: 'HOURS') {
        input message: 'Deploy to production?', submitter: 'admin,ops'
    }
}

node {
    stage('Deploy') {
        sh './deploy.sh'
    }
}
```
