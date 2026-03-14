# Common GitHub Actions Reference

Current as of early 2026. All SHAs are for the listed version; verify before use.

## Repository and Checkout

### actions/checkout v6.0.2
SHA: `de0fac2e4500dabe0009e67214ff5f5447ce83dd`

```yaml
# Basic
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    fetch-depth: 1

# Full history (for changelogs, tags)
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    fetch-depth: 0

# PR HEAD commit
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    ref: ${{ github.event.pull_request.head.sha }}

# Private repository
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
  with:
    repository: my-org/my-private-repo
    token: ${{ secrets.GH_PAT }}
```

Required permission: `contents: read`

## Language Setup

### actions/setup-node v6.2.0
SHA: `6044e13b5dc448c55e2357c09f80417699197238`

```yaml
- uses: actions/setup-node@6044e13b5dc448c55e2357c09f80417699197238 # v6.2.0
  with:
    node-version: '24'
    cache: 'npm'
    cache-dependency-path: '**/package-lock.json'
```

Node 20 default switch: March 4, 2026. EOL: April 2026.

### actions/setup-python v6.2.0
SHA: `a309ff8b426b58ec0e2a45f0f869d46889d02405`

```yaml
- uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
  with:
    python-version: '3.11'
    cache: 'pip'
    cache-dependency-path: 'requirements*.txt'
```

### actions/setup-java v4.0.0
SHA: `387ac29b308b003ca37ba93a6cab5eb57c8f5f93`

```yaml
- uses: actions/setup-java@387ac29b308b003ca37ba93a6cab5eb57c8f5f93 # v4.0.0
  with:
    distribution: 'temurin'
    java-version: '17'
    cache: 'maven'
```

### actions/setup-go v5.0.0
SHA: `0c52d547c9bc32b1aa3301fd7a9cb496313a4491`

```yaml
- uses: actions/setup-go@0c52d547c9bc32b1aa3301fd7a9cb496313a4491 # v5.0.0
  with:
    go-version: 'stable'
    cache-dependency-path: go.sum
```

## Caching and Artifacts

### actions/cache v5.0.3
SHA: `cdf6c1fa76f9f475f3d7449005a359c84ca0f306`

```yaml
- uses: actions/cache@cdf6c1fa76f9f475f3d7449005a359c84ca0f306 # v5.0.3
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('**/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-npm-
```

### actions/upload-artifact v4.3.1
SHA: `5d5d22a31266ced268874388b861e4b58bb5c2f3`

```yaml
- uses: actions/upload-artifact@5d5d22a31266ced268874388b861e4b58bb5c2f3 # v4.3.1
  with:
    name: build-${{ github.sha }}
    path: dist/
    retention-days: 7
    if-no-files-found: error
```

### actions/download-artifact v4.1.4
SHA: `c850b930e6ba138125429b7e5c93fc707a7f8427`

```yaml
- uses: actions/download-artifact@c850b930e6ba138125429b7e5c93fc707a7f8427 # v4.1.4
  with:
    name: build-${{ github.sha }}
    path: dist/
```

## Docker

### docker/setup-buildx-action v3.3.0
SHA: `d70bba72b1f3fd22344832f00baa16ece964efeb`

```yaml
- uses: docker/setup-buildx-action@d70bba72b1f3fd22344832f00baa16ece964efeb # v3.3.0
```

### docker/login-action v3.1.0
SHA: `e92390c5fb421da1463c202d546fed0ec5c39f20`

```yaml
# Docker Hub
- uses: docker/login-action@e92390c5fb421da1463c202d546fed0ec5c39f20 # v3.1.0
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}

# GHCR
- uses: docker/login-action@e92390c5fb421da1463c202d546fed0ec5c39f20 # v3.1.0
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

### docker/build-push-action v5.3.0
SHA: `2cdde995de11925a030ce8070c3d77a52ffcf1c0`

```yaml
- uses: docker/build-push-action@2cdde995de11925a030ce8070c3d77a52ffcf1c0 # v5.3.0
  with:
    context: .
    platforms: linux/amd64,linux/arm64
    push: true
    tags: |
      user/app:latest
      user/app:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## Cloud

### aws-actions/configure-aws-credentials v4.0.2
SHA: `e3dd6a429d7300a6a4c196c26e071d42e0343502`

```yaml
# OIDC (preferred -- no long-lived keys)
- uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502 # v4.0.2
  with:
    role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
    role-session-name: GitHubActions-${{ github.run_id }}
    aws-region: us-east-1
```

Required permission: `id-token: write`

## Security and Quality

### actions/dependency-review-action v4.8.3
SHA: `05fe4576374b728f0c523d6a13d64c25081e0803`

```yaml
- uses: actions/dependency-review-action@05fe4576374b728f0c523d6a13d64c25081e0803 # v4.8.3
  with:
    fail-on-severity: critical
    allow-licenses: MIT, Apache-2.0, BSD-3-Clause
```

### github/codeql-action v3.32.5
SHA: `ae9ef3a1d2e3413523c3741725c30064970cc0d4`

```yaml
- uses: github/codeql-action/init@ae9ef3a1d2e3413523c3741725c30064970cc0d4 # v3.32.5
  with:
    languages: javascript

- uses: github/codeql-action/upload-sarif@ae9ef3a1d2e3413523c3741725c30064970cc0d4 # v3.32.5
  if: always()
  with:
    sarif_file: results.sarif
```

Required permissions: `contents: read`, `security-events: write`

## Release

### softprops/action-gh-release v2.0.2
SHA: `9d7c94cfd0a1f3ed45544c887983e9fa900f0564`

```yaml
- uses: softprops/action-gh-release@9d7c94cfd0a1f3ed45544c887983e9fa900f0564 # v2.0.2
  with:
    name: Release ${{ github.ref_name }}
    body_path: CHANGELOG.md
    files: |
      dist/*.zip
      dist/*.tar.gz
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Finding Action Documentation

```
"[owner/repo] [version] github action documentation"
```

Verify latest SHA: `git ls-remote https://github.com/[owner]/[repo] [tag]`
