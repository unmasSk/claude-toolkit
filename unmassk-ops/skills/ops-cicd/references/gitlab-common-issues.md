# GitLab CI/CD Common Issues

## Syntax and Configuration

### Reserved keyword used as job name

```yaml
# causes: "Unknown parameter: image"
image:
  stage: build
  script: docker build .

# fix
build-image:
  stage: build
  script: docker build .
```

Reserved names: `image`, `services`, `stages`, `types`, `before_script`, `after_script`, `variables`, `cache`, `include`, `pages`, `default`, `workflow`.

### Missing `script` in job

Every job requires `script` (exception: `trigger` jobs).

### Stage not defined

A job's `stage` must be listed in the top-level `stages` array. If `stages` is omitted, only the defaults `.pre`, `build`, `test`, `deploy`, `.post` are valid.

### Mixing `rules` with `only`/`except`

Cannot use both in the same job — validation error. Migrate fully to `rules`.

---

## Dependencies and Artifacts

### Artifacts not available in downstream job

Artifacts pass automatically to all jobs in later stages (by default). When using `needs:`, only the listed jobs' artifacts are downloaded. To limit downloads explicitly:

```yaml
test:
  needs:
    - job: build-a
      artifacts: true
    - job: build-b
      artifacts: false   # don't download build-b artifacts
```

### Cache used instead of artifacts for build outputs

Cache is shared across pipelines (speed). Artifacts are shared within a pipeline (correctness). Build output (e.g., `dist/`) must be an artifact, not a cache entry.

### Circular `needs` dependency

GitLab will reject the pipeline with a validation error. Visualize the DAG before committing.

---

## Rules and Conditions

### `changes:` unreliable on branch pipelines

`changes:` without an `if:` condition evaluates against the previous commit on branch pipelines. Always pair it with an `if:` condition:

```yaml
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    changes:
      - src/**/*
  - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

### Conflicting rules — first rule matches

Rules evaluate top-down. A catch-all `when: always` earlier in the list will shadow later conditions.

---

## Docker and Services

### Service connection failure

```yaml
# wrong — no alias, no env vars
services:
  - postgres:15

# correct
services:
  - name: postgres:15
    alias: postgres
variables:
  POSTGRES_DB: testdb
  POSTGRES_USER: ci
  POSTGRES_PASSWORD: ci
  DATABASE_URL: postgres://ci:ci@postgres:5432/testdb
```

Connect to services by alias, not by `localhost`.

### Image pull failure

- Check image name and tag exist in the registry.
- For private registries, authenticate in `before_script` or configure runner credentials.
- Avoid `:latest` — use pinned versions.

---

## Performance

### High cache miss rate

```yaml
# bad — different key per commit
cache:
  key: $CI_COMMIT_SHA

# good — stable key tied to lockfile content
cache:
  key:
    files: [package-lock.json]
  paths: [node_modules/]
```

### Multiple jobs downloading same artifacts

Use `dependencies:` to restrict which jobs' artifacts each job downloads. Without it, all previous-stage artifacts are downloaded by default.

---

## Deployment

### Concurrent deployments causing conflicts

Add `resource_group: production` to deployment jobs. GitLab serializes jobs within the same resource group.

### Manual job does not block pipeline

`when: manual` alone does not block. To block, the manual job must be in `needs:` of a dependent job, and `allow_failure: false` (the default) must apply.

### Review app not stopped automatically

```yaml
deploy-review:
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    on_stop: stop-review
    auto_stop_in: 3 days

stop-review:
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  when: manual
```

`on_stop` and `auto_stop_in` both required for automatic cleanup.

---

## Include Files

### `local:` path not found

```yaml
# wrong — relative path
include:
  - local: templates/ci.yml

# correct — absolute from repo root
include:
  - local: /templates/ci.yml
```

### External project include fails

```yaml
# wrong — branch ref is mutable
include:
  - project: my-group/templates
    ref: main
    file: /build.yml

# correct — SHA or protected tag
include:
  - project: my-group/templates
    ref: v1.2.3
    file: /build.yml
```

---

## Debugging

Enable debug trace (non-production only):

```yaml
variables:
  CI_DEBUG_TRACE: "true"
```

Print environment context:

```yaml
debug:
  script:
    - env | sort
    - set -x && ./my-script.sh
```

Validate before pushing — use the CI Lint tool at: `CI/CD > Pipeline editor > Validate` or `POST /api/v4/ci/lint`.

Local execution: `gitlab-ci-local` (npm package).
