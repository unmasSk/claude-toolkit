# GitLab CI/CD YAML Reference

## File Structure

`.gitlab-ci.yml` must be at the repository root.

```yaml
# Global config
default:
  image: node:20-alpine
  cache: ...
  retry: ...

include:
  - local: '.gitlab/ci/build.yml'

stages:
  - build
  - test
  - deploy

variables:
  NODE_VERSION: "20"

workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

# Job definitions
job-name:
  stage: build
  script:
    - npm run build
```

## Global Keywords

### `stages`
```yaml
stages:
  - .pre      # runs before everything
  - build
  - test
  - deploy
  - .post     # runs after everything
```

### `default`
Applies to all jobs that don't override these keys. Supported: `image`, `services`, `before_script`, `after_script`, `cache`, `artifacts`, `retry`, `timeout`, `interruptible`, `tags`, `hooks`.

### `include`
```yaml
include:
  - local: '.gitlab/ci/build-jobs.yml'
  - project: 'group/ci-templates'
    ref: 'v1.2.3'       # use tags or SHAs, not branch refs
    file: 'templates/build.yml'
  - template: 'Security/SAST.gitlab-ci.yml'
  - component: gitlab.com/my-org/components/build@1.0.0
```

### `workflow`
```yaml
workflow:
  rules:
    - if: $CI_MERGE_REQUEST_ID
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG
  auto_cancel:
    on_new_commit: interruptible
```

## Job Keywords

### Execution
```yaml
job:
  stage: test
  image: node:20-alpine
  before_script:
    - npm ci
  script:
    - npm test
  after_script:          # separate shell, 5min timeout
    - rm -rf temp/
  when: on_success       # on_success | on_failure | always | manual | delayed | never
  allow_failure: true
  timeout: 30 minutes
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure
  interruptible: true    # can be cancelled
  resource_group: production   # prevents concurrent runs
```

### Artifacts and Cache
```yaml
build:
  script: npm run build
  artifacts:
    paths:
      - dist/
    exclude:
      - "**/*.map"
    expire_in: 1 hour
    when: on_success
    reports:
      junit: junit.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura-coverage.xml

test:
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - node_modules/
    policy: pull           # pull | push | pull-push
```

Cache vs artifacts: cache is for speed (dependencies between runs), artifacts are for passing files between jobs in the same pipeline.

### Rules (use instead of `only`/`except`)
```yaml
deploy:
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: always
    - if: $CI_MERGE_REQUEST_ID
      when: manual
    - changes:
        - src/**/*
    - exists:
        - Dockerfile
    - when: never
```

### Dependencies and Needs (DAG)
```yaml
build-a:
  stage: build
  script: build a
  artifacts:
    paths: [dist-a/]

build-b:
  stage: build
  script: build b
  artifacts:
    paths: [dist-b/]

test-a:
  stage: test
  needs: [build-a]           # starts as soon as build-a completes
  dependencies: [build-a]    # only download artifacts from build-a
  script: test dist-a/

deploy:
  stage: deploy
  needs:
    - job: build-a
      artifacts: true
    - job: test-a
      artifacts: false
  script: deploy
```

### Environment
```yaml
deploy-staging:
  environment:
    name: staging
    url: https://staging.example.com
    on_stop: stop-staging
    auto_stop_in: 1 day
    action: start   # start | prepare | stop

# Dynamic environment (review apps)
review:
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    url: https://$CI_COMMIT_REF_SLUG.review.example.com
    on_stop: stop-review
    auto_stop_in: 1 week
  rules:
    - if: $CI_MERGE_REQUEST_ID
```

### Parallel (matrix testing)
```yaml
test:
  parallel:
    matrix:
      - NODE_VERSION: ['18', '20', '22']
        OS: ['alpine', 'bookworm-slim']
  image: node:${NODE_VERSION}-${OS}
  script: npm test

# Split test suite
test-split:
  parallel: 5
  script: npm test -- --shard=${CI_NODE_INDEX}/${CI_NODE_TOTAL}
```

### Extends and Templates
```yaml
.deploy-base:
  before_script:
    - echo "Deploying to $ENVIRONMENT"
  retry:
    max: 2
    when: [runner_system_failure]
  resource_group: ${ENVIRONMENT}

deploy-staging:
  extends: .deploy-base
  variables:
    ENVIRONMENT: staging
  script: ./deploy.sh staging

deploy-production:
  extends: .deploy-base
  variables:
    ENVIRONMENT: production
  script: ./deploy.sh production
  when: manual
```

### Triggers (downstream pipelines)
```yaml
# Trigger another project
trigger-downstream:
  trigger:
    project: group/downstream
    branch: main
    strategy: depend

# Trigger child pipeline
trigger-child:
  trigger:
    include: child-pipeline.yml
    strategy: depend
```

## Predefined Variables (most common)

```yaml
$CI_COMMIT_SHA / $CI_COMMIT_SHORT_SHA
$CI_COMMIT_BRANCH / $CI_COMMIT_TAG
$CI_COMMIT_REF_NAME / $CI_COMMIT_REF_SLUG
$CI_PIPELINE_ID / $CI_PIPELINE_SOURCE
$CI_JOB_ID / $CI_JOB_NAME / $CI_JOB_STAGE
$CI_PROJECT_DIR / $CI_PROJECT_PATH
$CI_REGISTRY / $CI_REGISTRY_IMAGE
$CI_REGISTRY_USER / $CI_REGISTRY_PASSWORD
$CI_MERGE_REQUEST_ID / $CI_MERGE_REQUEST_IID
$CI_NODE_INDEX / $CI_NODE_TOTAL   # for parallel jobs
```

## Reserved Job Names

Cannot be used as job names: `image`, `services`, `stages`, `types`, `before_script`, `after_script`, `variables`, `cache`, `include`, `pages`, `default`, `workflow`

## YAML Anchors

```yaml
.retry-config: &retry-config
  retry:
    max: 2
    when: [runner_system_failure]

job1:
  <<: *retry-config
  script: command1

job2:
  <<: *retry-config
  script: command2
```
