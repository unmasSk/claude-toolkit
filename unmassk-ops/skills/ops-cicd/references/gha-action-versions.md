# GitHub Actions Version Reference

## Current Recommended Versions (2026)

| Action | Version | SHA | Notes |
|---|---|---|---|
| `actions/checkout` | v6 | `de0fac2e4500dabe0009e67214ff5f5447ce83dd` | Stores credentials in $RUNNER_TEMP |
| `actions/setup-node` | v6 | `6044e13b5dc448c55e2357c09f80417699197238` | Node 24 support |
| `actions/setup-python` | v6 | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | Python 3.13 support |
| `actions/setup-java` | v4 | `387ac29b308b003ca37ba93a6cab5eb57c8f5f93` | |
| `actions/setup-go` | v5 | `0c52d547c9bc32b1aa3301fd7a9cb496313a4491` | Go 1.23+ |
| `actions/cache` | v5 | `cdf6c1fa76f9f475f3d7449005a359c84ca0f306` | Node 24 runtime, runner v2.327.1+ required |
| `actions/upload-artifact` | v4 | `5d5d22a31266ced268874388b861e4b58bb5c2f3` | v3 deprecated |
| `actions/download-artifact` | v4 | `c850b930e6ba138125429b7e5c93fc707a7f8427` | v3 deprecated |
| `docker/setup-buildx-action` | v3 | `d70bba72b1f3fd22344832f00baa16ece964efeb` | |
| `docker/login-action` | v3 | `e92390c5fb421da1463c202d546fed0ec5c39f20` | |
| `docker/build-push-action` | v6 | (check releases) | Provenance attestation |
| `docker/metadata-action` | v5 | (check releases) | |
| `aws-actions/configure-aws-credentials` | v4 | `e3dd6a429d7300a6a4c196c26e071d42e0343502` | OIDC support |

## Version Pinning

```yaml
# Recommended: SHA + version comment
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

# Acceptable: major version tag (official GitHub actions only)
- uses: actions/checkout@v6

# Never: branch reference
- uses: actions/checkout@main
```

Find SHA for a tag:
```bash
git ls-remote https://github.com/actions/checkout v6.0.2
```

## Node.js Runtime Timeline

| Runtime | Status |
|---|---|
| Node.js 12 | EOL April 2022 -- deprecated |
| Node.js 16 | EOL September 2023 -- deprecated |
| Node.js 20 | EOL April 2026 -- default switch March 4, 2026 |
| Node.js 22/24 | Current LTS |

Actions using v1/v2/v3 of most actions (checkout, cache, etc.) run on deprecated Node runtimes and will emit warnings.

## Version Validation Process

1. Extract all `uses:` statements from the workflow.
2. Compare each action version against the table above.
3. Flag: **DEPRECATED** (below minimum), **OUTDATED** (older major), **UP-TO-DATE**.

```
actions/checkout@v6.0.2   -- UP-TO-DATE
docker/build-push-action@v5 -- OUTDATED (current: v6)
actions/upload-artifact@v3  -- DEPRECATED (minimum: v4)
```

## Dependabot for Automatic Updates

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

## Cache Storage (2025)

- 10 GB free per repository.
- Additional storage available (Pro/Team/Enterprise).
- Legacy cache service retired February 1, 2025 -- requires cache v4.2.0+.
- `actions/cache` v5 requires runner v2.327.1+.
