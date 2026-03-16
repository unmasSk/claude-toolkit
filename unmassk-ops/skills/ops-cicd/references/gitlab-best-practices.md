# GitLab CI/CD Best Practices

## Pipeline Design

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG
    - when: never

stages:
  - .pre
  - build
  - test
  - security
  - deploy
  - .post
```

Use `workflow:rules` to prevent duplicate pipelines on MR branches. Define all stages explicitly.

---

## DAG with `needs`

Start jobs as soon as their specific dependencies finish — do not wait for an entire stage.

```yaml
build-frontend:
  stage: build
  script: npm run build:frontend
  artifacts:
    paths: [frontend/dist/]
    expire_in: 1 hour

build-backend:
  stage: build
  script: go build ./cmd/server
  artifacts:
    paths: [backend/bin/]
    expire_in: 1 hour

test-frontend:
  stage: test
  needs: [build-frontend]
  script: npm test

test-backend:
  stage: test
  needs: [build-backend]
  script: go test ./...

deploy:
  stage: deploy
  needs: [test-frontend, test-backend]
  script: ./deploy.sh
  resource_group: production
  when: manual
```

Security scans that need no build artifacts can set `needs: []` to run immediately.

---

## Rules (not `only`/`except`)

```yaml
deploy-production:
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
      when: manual
    - if: $CI_PIPELINE_SOURCE == "schedule"
      when: never
    - when: never
```

Rules are evaluated top-down, first match wins. Cannot mix `rules` with `only`/`except` in the same job.

Changes-based filtering (use with `if` for reliability):

```yaml
test-frontend:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - frontend/**/*
        - package.json
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

`changes:` alone on branch pipelines evaluates against the previous commit, which can be unreliable.

---

## Caching

```yaml
variables:
  CACHE_VERSION: "v1"

.npm-cache:
  cache:
    key: ${CACHE_VERSION}-${CI_COMMIT_REF_SLUG}
    paths:
      - .npm/
      - node_modules/
    policy: pull-push

install:
  extends: .npm-cache
  script: npm ci --cache .npm

test:
  extends: .npm-cache
  cache:
    policy: pull    # read-only
  needs: [install]
  script: npm test
```

Use `CACHE_VERSION` to bust cache on demand. Set `policy: pull` on all jobs that do not update dependencies.

---

## Artifacts

```yaml
build:
  script: npm run build
  artifacts:
    paths:
      - dist/
    exclude:
      - "**/*.map"
      - "**/*.env"
    expire_in: 1 hour
    when: on_success

test:
  script: npm test
  artifacts:
    when: always
    expire_in: 2 days
    reports:
      junit: junit.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage/cobertura.xml
```

Cache is for reuse between pipeline runs (dependencies). Artifacts are for passing files within a pipeline (build outputs). Never put both in the same bucket.

Use `dependencies: [specific-job]` to avoid downloading every upstream artifact.

---

## Deployment Gates

```yaml
.deploy-base:
  retry:
    max: 2
    when: [runner_system_failure]
  resource_group: ${ENVIRONMENT}
  interruptible: false

deploy-staging:
  extends: .deploy-base
  variables:
    ENVIRONMENT: staging
  environment:
    name: staging
    url: https://staging.example.com
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy-production:
  extends: .deploy-base
  variables:
    ENVIRONMENT: production
  environment:
    name: production
    url: https://example.com
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
  when: manual
  needs: [deploy-staging]
```

`resource_group` prevents concurrent deploys to the same environment. Always `manual` for production. Use `interruptible: false` on deploy jobs — never cancel a deployment in progress.

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

## Reusability

Prefer `extends` over YAML anchors for job templates — anchors don't work across `include` files.

```yaml
# .gitlab/ci/templates.yml
.node-base:
  image: node:20-alpine
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths: [node_modules/]
  before_script: [npm ci]

# .gitlab-ci.yml
include:
  - local: .gitlab/ci/templates.yml

build:
  extends: .node-base
  stage: build
  script: npm run build
```

For shared templates across projects, pin `ref` to a SHA or protected tag — not a branch name.

---

## Anti-Patterns

| Anti-pattern | Fix |
|---|---|
| `image: node:latest` | Pin to `node:20.x-alpine3.xx` |
| `only: [main]` | Use `rules:` |
| No `expire_in` on artifacts | Set `expire_in: 1 hour` for intermediates |
| No `resource_group` on deploy | Add `resource_group: ${ENVIRONMENT}` |
| `cache` for build outputs | Use `artifacts` instead |
| `dependencies: []` missing | Explicitly limit artifact downloads |
| No timeout on jobs | Set `timeout:` on all long-running jobs |
| `interruptible: true` on deploy | Only test jobs should be interruptible |
