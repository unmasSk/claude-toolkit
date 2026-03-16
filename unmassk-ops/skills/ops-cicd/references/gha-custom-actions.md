# Custom GitHub Actions

## Action Types

| Type | Runtime | Use Case |
|---|---|---|
| Composite | Shell/Actions | Combine multiple steps, fastest startup |
| Docker | Container | Custom environment, specific tools |
| JavaScript | Node.js | API interactions, complex logic |

## Directory Structure

### Repository-local actions
```
.github/
  actions/
    setup-node-cached/     # composite
      action.yml
    terraform-validator/   # docker
      action.yml
      Dockerfile
      entrypoint.sh
    label-pr/              # javascript
      action.yml
      dist/index.js        # compiled -- must be committed
      src/index.ts
  workflows/
    ci.yml
```

### Standalone action repository
```
action-root/
  action.yml          # MUST be in root
  README.md
  dist/               # compiled JS (for JS actions)
  src/
  Dockerfile          # for Docker actions
```

Usage:
```yaml
# Local action
- uses: ./.github/actions/setup-node-cached
  with:
    node-version: '20'

# External action
- uses: owner/repo/.github/actions/action-name@v1
```

## action.yml Templates

### Composite
```yaml
name: 'Setup Node with Cache'
description: 'Setup Node.js with automatic caching'
author: 'Your Org'

inputs:
  node-version:
    description: 'Node.js version'
    required: true
    default: '20'

outputs:
  cache-hit:
    description: 'Whether cache was restored'
    value: ${{ steps.cache.outputs.cache-hit }}

runs:
  using: 'composite'
  steps:
    - name: Setup Node
      id: setup
      shell: bash
      run: echo "value=result" >> $GITHUB_OUTPUT
```

### Docker
```yaml
name: 'My Docker Action'
description: 'Runs in a container'

inputs:
  input-name:
    description: 'Input description'
    required: true

runs:
  using: 'docker'
  image: 'Dockerfile'
  args:
    - ${{ inputs.input-name }}
```

### JavaScript
```yaml
name: 'My JS Action'
description: 'Runs on Node'

inputs:
  github-token:
    description: 'GitHub token'
    required: true

runs:
  using: 'node20'
  main: 'dist/index.js'
```

## Versioning

```bash
# Create version tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Update major version tag (points to latest v1.x.x)
git tag -fa v1 -m "Update v1 to v1.0.0"
git push origin v1 --force
```

Users can reference:
```yaml
- uses: owner/action@v1.0.0   # pinned
- uses: owner/action@v1       # latest v1.x.x
- uses: owner/action@abc123   # SHA (most secure)
```

## Release Workflow

```yaml
on:
  push:
    tags: ['v*']

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - name: Create release
        run: gh release create ${{ github.ref_name }} --generate-notes
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Update major tag
        run: |
          MAJOR=$(echo ${{ github.ref_name }} | cut -d. -f1)
          git tag -fa $MAJOR -m "Update $MAJOR"
          git push origin $MAJOR --force
```

## Marketplace Requirements

- Repository must be public.
- `action.yml` in repository root.
- Branding metadata (icon and color) in action.yml.
- README.md with usage examples.
- Semantic version tags.

Branding example:
```yaml
branding:
  icon: 'package'
  color: 'blue'
```
