# GitLab CI/CD Common Patterns

## Standard Node.js Pipeline

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG

stages: [build, test, deploy]

default:
  image: node:20-alpine
  cache:
    key:
      files: [package-lock.json]
    paths: [.npm/, node_modules/]

build:
  stage: build
  script: [npm ci --cache .npm, npm run build]
  cache:
    policy: pull-push
  artifacts:
    paths: [dist/]
    expire_in: 1 hour

test-unit:
  stage: test
  needs: [build]
  script: npm test
  coverage: '/Lines\s*:\s*(\d+\.?\d*)%/'
  artifacts:
    when: always
    reports:
      junit: junit.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura.xml

deploy-staging:
  stage: deploy
  needs: [test-unit]
  script: ./deploy.sh staging
  environment:
    name: staging
    url: https://staging.example.com
  resource_group: staging
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy-production:
  stage: deploy
  needs: [deploy-staging]
  script: ./deploy.sh production
  environment:
    name: production
    url: https://example.com
  resource_group: production
  when: manual
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
```

---

## Docker Build — DinD

```yaml
variables:
  DOCKER_TLS_CERTDIR: "/certs"
  IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA

build-image:
  stage: build
  image: docker:25-dind
  services:
    - docker:25-dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build --cache-from $CI_REGISTRY_IMAGE:latest --tag $IMAGE --tag $CI_REGISTRY_IMAGE:latest .
    - docker push $IMAGE
    - docker push $CI_REGISTRY_IMAGE:latest
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Docker Build — Kaniko (no root, no DinD)

```yaml
build-kaniko:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:v1.23.0-debug
    entrypoint: [""]
  script:
    - mkdir -p /kaniko/.docker
    - echo "{\"auths\":{\"$CI_REGISTRY\":{\"auth\":\"$(printf "%s:%s" "$CI_REGISTRY_USER" "$CI_REGISTRY_PASSWORD" | base64 | tr -d '\n')\"}}}" > /kaniko/.docker/config.json
    - /kaniko/executor --context $CI_PROJECT_DIR --dockerfile Dockerfile --destination $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA --cache=true
```

Kaniko is preferred for shared runners — no privileged mode required.

---

## Matrix Testing

```yaml
test-matrix:
  stage: test
  parallel:
    matrix:
      - NODE: ['18', '20', '22']
        OS: ['alpine', 'bookworm-slim']
  image: node:${NODE}-${OS}
  script: npm test
```

---

## Integration Tests with Services

```yaml
test-integration:
  stage: test
  image: node:20-alpine
  services:
    - name: postgres:16-alpine
      alias: postgres
    - name: redis:7-alpine
      alias: redis
  variables:
    POSTGRES_DB: testdb
    POSTGRES_USER: ci
    POSTGRES_PASSWORD: ci
    DATABASE_URL: postgres://ci:ci@postgres:5432/testdb
    REDIS_URL: redis://redis:6379
  script: npm run test:integration
  retry:
    max: 2
    when: [runner_system_failure, stuck_or_timeout_failure]
```

---

## Security Scanning (Built-in Templates)

```yaml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Dependency-Scanning.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml

container_scanning:
  variables:
    CS_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
  needs: [build-image]
```

---

## Kubernetes Deployment — Helm

```yaml
deploy-helm:
  stage: deploy
  image: alpine/helm:3.14.4
  before_script:
    - kubectl config use-context $KUBE_CONTEXT
  script:
    - helm upgrade --install myapp ./helm
        --namespace $ENVIRONMENT
        --create-namespace
        --set image.tag=$CI_COMMIT_SHORT_SHA
        --wait --timeout 5m
  environment:
    name: $ENVIRONMENT
    kubernetes:
      namespace: $ENVIRONMENT
  resource_group: $ENVIRONMENT
  when: manual
```

---

## Monorepo — Conditional by Changed Path

```yaml
build-frontend:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: [frontend/**/*]
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

build-backend:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: [backend/**/*]
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Monorepo — Parent/Child Pipelines

```yaml
# root .gitlab-ci.yml
trigger-frontend:
  stage: trigger
  trigger:
    include: frontend/.gitlab-ci.yml
    strategy: depend
  rules:
    - changes: [frontend/**/*]

trigger-backend:
  stage: trigger
  trigger:
    include: backend/.gitlab-ci.yml
    strategy: depend
  rules:
    - changes: [backend/**/*]
```

---

## Dynamic Child Pipeline

```yaml
generate-pipeline:
  stage: .pre
  script: python scripts/gen-pipeline.py > generated.yml
  artifacts:
    paths: [generated.yml]

run-child:
  stage: build
  trigger:
    include:
      - artifact: generated.yml
        job: generate-pipeline
    strategy: depend
  needs: [generate-pipeline]
```

---

## Multi-Project Trigger

```yaml
trigger-deployment:
  stage: deploy
  trigger:
    project: group/deploy-project
    branch: main
    strategy: depend
  variables:
    SERVICE_VERSION: $CI_COMMIT_SHORT_SHA
    ENVIRONMENT: production
  when: manual
  rules:
    - if: $CI_COMMIT_TAG
```

---

## Review Apps

```yaml
deploy-review:
  stage: deploy
  script: ./deploy-review.sh $CI_COMMIT_REF_SLUG
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: https://$CI_ENVIRONMENT_SLUG.review.example.com
    on_stop: stop-review
    auto_stop_in: 3 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

stop-review:
  stage: deploy
  script: ./stop-review.sh $CI_COMMIT_REF_SLUG
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  when: manual
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

---

## Release Job

```yaml
create-release:
  stage: .post
  image: registry.gitlab.com/gitlab-org/release-cli:latest
  script: echo "Creating release $CI_COMMIT_TAG"
  release:
    tag_name: $CI_COMMIT_TAG
    name: "Release $CI_COMMIT_TAG"
    description: $CI_COMMIT_MESSAGE
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
```
