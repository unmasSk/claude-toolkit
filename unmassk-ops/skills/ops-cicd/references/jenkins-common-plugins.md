# Jenkins Common Plugins

## Git Plugin

```groovy
// auto-detect from job config
checkout scm

// explicit, shallow
checkout scmGit(
    branches: [[name: '*/main']],
    userRemoteConfigs: [[
        url: 'https://github.com/org/repo.git',
        credentialsId: 'github-credentials'
    ]],
    extensions: [cloneOption(shallow: true, depth: 1)]
)
```

Environment variables set by the plugin: `GIT_COMMIT`, `GIT_BRANCH`, `GIT_URL`, `GIT_PREVIOUS_COMMIT`, `GIT_PREVIOUS_SUCCESSFUL_COMMIT`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`.

---

## Docker Plugin (docker-workflow)

```groovy
// declarative agent
agent {
    docker {
        image 'maven:3.9.11-eclipse-temurin-21'
        args  '-v $HOME/.m2:/root/.m2'
        reuseNode true
    }
}

// from Dockerfile
agent {
    dockerfile {
        filename 'Dockerfile.build'
        additionalBuildArgs '--build-arg VERSION=1.0'
    }
}

// scripted — run inside image
docker.image('maven:3.9.11-eclipse-temurin-21').inside('-v $HOME/.m2:/root/.m2') {
    sh 'mvn clean package'
}

// build and push
def img = docker.build("myapp:${env.BUILD_NUMBER}")
docker.withRegistry('https://registry.example.com', 'registry-creds') {
    img.push()
    img.push('latest')
}

// sidecar
docker.image('postgres:16').withRun('-e POSTGRES_PASSWORD=test') { db ->
    docker.image('maven:3.9.11').inside("--link ${db.id}:postgres") {
        sh 'mvn verify'
    }
}
```

---

## Kubernetes Plugin

```groovy
// declarative
agent {
    kubernetes {
        yaml '''
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  containers:
  - name: maven
    image: maven:3.9.11-eclipse-temurin-21
    command: [cat]
    tty: true
    resources:
      requests: { memory: 1Gi, cpu: 500m }
      limits:   { memory: 2Gi, cpu: 1000m }
  - name: docker
    image: docker:24
    command: [cat]
    tty: true
    volumeMounts:
    - name: docker-sock
      mountPath: /var/run/docker.sock
  volumes:
  - name: docker-sock
    hostPath: { path: /var/run/docker.sock }
'''
    }
}

// use specific container in a step
stage('Build') {
    steps {
        container('maven') {
            sh 'mvn clean package'
        }
    }
}

// scripted pod template
podTemplate(
    containers: [
        containerTemplate(name: 'maven', image: 'maven:3.9.11', ttyEnabled: true, command: 'cat'),
        containerTemplate(name: 'kubectl', image: 'bitnami/kubectl:1.29', ttyEnabled: true, command: 'cat')
    ],
    volumes: [secretVolume(secretName: 'kubeconfig', mountPath: '/root/.kube')]
) {
    node(POD_LABEL) {
        container('maven') { sh 'mvn package' }
        container('kubectl') { sh 'kubectl apply -f k8s/' }
    }
}
```

---

## Credentials Plugin

```groovy
withCredentials([
    usernamePassword(credentialsId: 'docker-hub', usernameVariable: 'USER', passwordVariable: 'PASS'),
    string(credentialsId: 'api-token', variable: 'TOKEN'),
    sshUserPrivateKey(credentialsId: 'deploy-key', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
    file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG'),
    certificate(credentialsId: 'code-sign', keystoreVariable: 'KS', passwordVariable: 'KS_PASS')
]) {
    sh 'docker login -u $USER -p $PASS'
}

// declarative binding — creates VAR_USR and VAR_PSW
environment {
    DOCKER_CREDS = credentials('docker-hub')
    API_KEY      = credentials('api-token')
}
```

---

## Pipeline Utility Steps

```groovy
// files
def content = readFile 'version.txt'
writeFile file: 'out.txt', text: 'done'

// JSON
def cfg = readJSON file: 'config.json'
writeJSON file: 'out.json', json: [name: 'app', version: '1.0']

// YAML
def spec = readYAML file: 'values.yaml'
writeYAML file: 'out.yaml', data: [replicas: 3]

// properties
def props = readProperties file: 'build.properties'

// filesystem
if (fileExists('marker.txt')) { echo 'exists' }
def jars = findFiles glob: 'target/**/*.jar'

// zip
zip   zipFile: 'dist.zip', dir: 'dist'
unzip zipFile: 'dist.zip', dir: 'output'
```

---

## JUnit Plugin

```groovy
post {
    always {
        junit(
            testResults: '**/surefire-reports/*.xml',
            allowEmptyResults: true,
            keepLongStdio: true
        )
    }
}
```

---

## HTML Publisher

```groovy
publishHTML([
    reportDir:   'coverage',
    reportFiles: 'index.html',
    reportName:  'Coverage Report',
    keepAll:     true,
    allowMissing: false
])
```

---

## Slack Notification Plugin

```groovy
slackSend(
    color:             currentBuild.result == 'SUCCESS' ? 'good' : 'danger',
    message:           "Build ${env.JOB_NAME} #${env.BUILD_NUMBER}: ${currentBuild.result}",
    channel:           '#ci',
    tokenCredentialId: 'slack-token'
)
```

Use `fixed` and `regression` post conditions to notify only on state change:

```groovy
post {
    failure   { slackSend color: 'danger', message: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER}" }
    fixed     { slackSend color: 'good',   message: "FIXED:  ${env.JOB_NAME} #${env.BUILD_NUMBER}" }
}
```

---

## Email Extension Plugin

```groovy
emailext(
    subject: "Build ${currentBuild.result}: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
    body: '<p>Build URL: <a href="${BUILD_URL}">${BUILD_URL}</a></p>',
    to: 'team@example.com',
    mimeType: 'text/html',
    attachLog: true,
    recipientProviders: [developers(), culprits(), requestor()]
)
```

---

## Workspace Cleanup Plugin

```groovy
cleanWs()    // in post { always } or scripted finally

cleanWs(
    deleteDirs: true,
    patterns: [
        [pattern: 'target', type: 'INCLUDE'],
        [pattern: '*.log',  type: 'INCLUDE']
    ]
)
```

---

## SonarQube Plugin

```groovy
stage('Analysis') {
    steps {
        withSonarQubeEnv('sonarqube-server') {
            sh 'mvn sonar:sonar'
        }
    }
}

stage('Quality Gate') {
    steps {
        timeout(time: 5, unit: 'MINUTES') {
            waitForQualityGate abortPipeline: true
        }
    }
}
```

The SonarQube Server URL in Jenkins configuration must not have a trailing slash.

---

## AWS Steps Plugin

```groovy
withAWS(credentials: 'aws-creds', region: 'us-east-1') {
    s3Upload bucket: 'my-bucket', path: 'artifacts/', includePathPattern: '**/*.jar'
    s3Download bucket: 'my-bucket', path: 'config/', file: 'config.json'
    def login = ecrLogin()
    sh login
}
```

---

## HTTP Request Plugin

```groovy
def response = httpRequest(
    url:            'https://api.example.com/deploy',
    httpMode:       'POST',
    contentType:    'APPLICATION_JSON',
    requestBody:    '{"env":"production"}',
    validResponseCodes: '200:299',
    timeout: 30
)
echo "Status: ${response.status}"
```

---

## OWASP Dependency-Check Plugin

```groovy
stage('Dependency Scan') {
    steps {
        dependencyCheck(
            additionalArguments: '--scan . --format XML --out dependency-check-report --failOnCVSS 7',
            odcInstallation: 'OWASP-Dependency-Check'
        )
    }
    post {
        always {
            dependencyCheckPublisher(
                pattern:              '**/dependency-check-report.xml',
                failedTotalCritical:  0,
                failedTotalHigh:      5
            )
        }
    }
}
```

---

## GitHub Plugin

```groovy
githubNotify status: 'PENDING', description: 'Build in progress', context: 'jenkins/build'

post {
    success { githubNotify status: 'SUCCESS', description: 'Build passed',  context: 'jenkins/build' }
    failure { githubNotify status: 'FAILURE', description: 'Build failed', context: 'jenkins/build' }
}
```

---

## Build steps (built-in)

```groovy
// trigger downstream job
build job: 'downstream-job',
    parameters: [string(name: 'ENV', value: 'production')],
    wait: true,
    propagate: true

// stash / unstash across nodes
stash   name: 'artifacts', includes: 'target/*.jar'
unstash 'artifacts'

// archive
archiveArtifacts artifacts: 'target/*.jar', fingerprint: true, onlyIfSuccessful: true

// retry / sleep
retry(3) { sh 'flaky-cmd' }
sleep time: 30, unit: 'SECONDS'

// wait for condition
waitUntil {
    sh(script: 'check-ready.sh', returnStatus: true) == 0
}
```

---

## Plugin discovery

- Official index: `https://plugins.jenkins.io/`
- Pipeline steps reference: `https://www.jenkins.io/doc/pipeline/steps/`
- Source: `https://github.com/jenkinsci/<plugin-name>-plugin`
