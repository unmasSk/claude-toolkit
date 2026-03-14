# Jenkins Declarative Pipeline Syntax

## Skeleton

```groovy
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
        timeout(time: 1, unit: 'HOURS')
        timestamps()
    }

    environment {
        APP_NAME = 'myapp'
        VERSION   = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Build') {
            steps {
                sh 'make build'
            }
        }
    }

    post {
        always  { cleanWs() }
        success { slackSend color: 'good', message: "Build ${env.BUILD_NUMBER} passed" }
        failure { slackSend color: 'danger', message: "Build ${env.BUILD_NUMBER} failed" }
    }
}
```

---

## agent

```groovy
agent any                          // any available executor

agent { label 'linux' }            // labeled node

agent {
    docker {
        image 'maven:3.9.11-eclipse-temurin-21'
        args '-v $HOME/.m2:/root/.m2'
        reuseNode true
    }
}

agent {
    kubernetes {
        yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: maven
    image: maven:3.9.11-eclipse-temurin-21
    command: [cat]
    tty: true
    resources:
      requests: { memory: 1Gi, cpu: 500m }
      limits:   { memory: 2Gi, cpu: 1000m }
'''
    }
}

agent none    // per-stage agents required
```

---

## options

```groovy
options {
    buildDiscarder(logRotator(
        numToKeepStr: '10',
        daysToKeepStr: '30',
        artifactNumToKeepStr: '5'
    ))
    disableConcurrentBuilds()
    timeout(time: 1, unit: 'HOURS')
    timestamps()
    skipDefaultCheckout()
    parallelsAlwaysFailFast()
    retry(1)
}
```

---

## environment

```groovy
environment {
    PLAIN_VAR         = 'value'
    SECRET_TEXT       = credentials('my-secret-id')              // string
    DOCKER_CREDS      = credentials('docker-hub')                // creates _USR and _PSW vars
    BUILD_TAG         = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"
}
```

---

## parameters

```groovy
parameters {
    string(name: 'DEPLOY_ENV', defaultValue: 'staging', description: 'Target environment')
    choice(name: 'VERSION', choices: ['1.0', '1.1', '2.0'], description: '')
    booleanParam(name: 'RUN_TESTS', defaultValue: true, description: '')
    password(name: 'SECRET', defaultValue: '', description: '')
}
// access: params.DEPLOY_ENV
```

---

## triggers

```groovy
triggers {
    cron('H 2 * * 1-5')                    // weekdays at ~2 AM
    pollSCM('H/15 * * * *')               // polling fallback (prefer webhooks)
    upstream(upstreamProjects: 'job-a,job-b', threshold: hudson.model.Result.SUCCESS)
}
```

---

## when

```groovy
stage('Deploy') {
    when {
        branch 'main'
        // OR
        expression { return params.DEPLOY_ENV == 'production' }
        // OR
        allOf {
            branch 'main'
            environment name: 'READY', value: 'true'
        }
        // OR
        anyOf { branch 'main'; branch 'release' }
        // OR
        not { branch 'develop' }
        // OR
        tag 'v*'
        // OR
        changeRequest()    // PR build
    }
    steps { sh './deploy.sh' }
}
```

---

## post

```groovy
post {
    always    { cleanWs() }
    success   { archiveArtifacts 'dist/**' }
    failure   { mail to: 'team@example.com', subject: "FAILED: ${env.JOB_NAME}", body: env.BUILD_URL }
    unstable  { echo 'Some tests failed' }
    fixed     { slackSend color: 'good', message: 'Build fixed' }
    regression { slackSend color: 'danger', message: 'Build regressed' }
    aborted   { echo 'Build was aborted' }
    cleanup   { deleteDir() }      // runs last, after all other post conditions
}
```

---

## parallel

```groovy
stage('Test') {
    failFast true
    parallel {
        stage('Unit') {
            agent { label 'linux' }
            steps { sh 'make test:unit' }
        }
        stage('Integration') {
            agent { label 'linux' }
            steps { sh 'make test:integration' }
        }
    }
    post {
        always { junit '**/test-results/*.xml' }
    }
}
```

---

## matrix

```groovy
stage('Cross-platform') {
    matrix {
        axes {
            axis { name 'PLATFORM'; values 'linux', 'mac', 'windows' }
            axis { name 'BROWSER';  values 'chrome', 'firefox' }
        }
        excludes {
            exclude {
                axis { name 'PLATFORM'; values 'linux' }
                axis { name 'BROWSER';  values 'firefox' }
            }
        }
        stages {
            stage('Test') {
                steps { echo "Testing on ${PLATFORM} / ${BROWSER}" }
            }
        }
    }
}
```

---

## input (gate before steps — frees agent while waiting)

```groovy
stage('Deploy to Production') {
    input {
        message 'Deploy to production?'
        ok 'Deploy'
        submitter 'admin,ops'
        parameters {
            string(name: 'VERSION', description: 'Version to deploy')
        }
    }
    steps { sh './deploy.sh ${VERSION}' }
}
```

Do not put `input` inside `steps {}` — it holds the agent during the wait.

---

## Common steps

```groovy
steps {
    sh 'single command'
    sh '''
        multi
        line
        commands
    '''
    sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
    bat 'windows-command'
    echo 'message'
    error 'fail with message (no stack trace)'

    retry(3) { sh 'flaky-command' }
    timeout(time: 5, unit: 'MINUTES') { sh 'slow-command' }

    withCredentials([
        usernamePassword(credentialsId: 'docker-hub', usernameVariable: 'USER', passwordVariable: 'PASS'),
        string(credentialsId: 'api-token', variable: 'TOKEN')
    ]) {
        sh 'docker login -u $USER -p $PASS'
    }

    stash   name: 'artifacts', includes: 'target/*.jar'
    unstash 'artifacts'

    archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
    junit '**/target/surefire-reports/*.xml'

    script {
        def val = sh(script: 'date +%s', returnStdout: true).trim()
        env.TIMESTAMP = val
    }

    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
        sh 'npm run test:integration'
    }

    cleanWs()
}
```

---

## Built-in variables

```groovy
env.BUILD_NUMBER        // "42"
env.BUILD_URL           // "https://jenkins.example.com/job/..."
env.JOB_NAME            // "my-pipeline"
env.BRANCH_NAME         // multibranch only
env.CHANGE_ID           // PR number (multibranch)
env.GIT_COMMIT
env.WORKSPACE

currentBuild.result          // SUCCESS, FAILURE, UNSTABLE, ABORTED, null (in-progress)
currentBuild.currentResult
currentBuild.number
currentBuild.displayName
currentBuild.description

params.PARAM_NAME
```
