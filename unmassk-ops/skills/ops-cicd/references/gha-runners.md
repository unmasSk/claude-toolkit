# GitHub-Hosted Runners Reference

## Standard Runner Labels

### Ubuntu
```yaml
runs-on: ubuntu-latest      # Ubuntu 24.04
runs-on: ubuntu-24.04
runs-on: ubuntu-22.04
runs-on: ubuntu-20.04
```

### Windows
```yaml
runs-on: windows-latest     # Windows Server 2022
runs-on: windows-2025       # Windows Server 2025
runs-on: windows-2022
runs-on: windows-2019
```

### macOS
```yaml
runs-on: macos-latest       # macOS 15, Apple Silicon
runs-on: macos-15           # macOS 15 Sequoia, M1/M2/M3
runs-on: macos-14           # macOS 14 Sonoma, M1/M2
runs-on: macos-26           # macOS 26 (PREVIEW)
# RETIRED: macos-13 (November 14, 2025) -- will fail if used
# RETIRED: macos-12
```

## ARM64 Runners

Available since August 2025. Free for public repositories.

```yaml
runs-on: ubuntu-latest-arm64
runs-on: ubuntu-24.04-arm64
runs-on: windows-latest-arm64
```

Specs: 4 vCPU ARM64, native execution. Private repos require GitHub Enterprise Cloud.

Multi-architecture build example:
```yaml
strategy:
  matrix:
    include:
      - runner: ubuntu-latest
        arch: x64
      - runner: ubuntu-latest-arm64
        arch: arm64

runs-on: ${{ matrix.runner }}
```

## GPU Runners

Requires Team or Enterprise Cloud plan.

```yaml
runs-on: gpu-t4-4-core    # NVIDIA Tesla T4
```

Specs: T4 GPU (16GB VRAM), 4 vCPU, 28GB RAM. Pricing: $0.07/min.

## M2 Pro macOS (Larger Runners)

```yaml
runs-on: macos-15-xlarge     # M2 Pro, 5-core, 14GB RAM
runs-on: macos-14-xlarge     # M2 Pro
```

Pricing: $0.16/min. Up to 15% faster than M1 runners. GPU acceleration enabled by default.

## Intel macOS (Long-term Deprecated)

```yaml
runs-on: macos-15-intel      # Intel x86_64 -- deprecated long-term
runs-on: macos-14-large      # Intel x86_64
```

Apple Silicon will be required after Fall 2027.

## Self-Hosted Runner Configuration

Configure actionlint to recognize custom labels:

```yaml
# .github/actionlint.yaml
self-hosted-runner:
  labels:
    - my-custom-runner
    - gpu-runner
    - on-premises
```

## Selection Guide

| Need | Runner |
|---|---|
| Most CI workloads | `ubuntu-latest` |
| iOS/macOS builds | `macos-latest` (Apple Silicon) |
| Multi-arch builds | `ubuntu-latest` + `ubuntu-latest-arm64` |
| ML/AI GPU workloads | `gpu-t4-4-core` |
| Heavy Xcode builds | `macos-15-xlarge` |
| ARM64 native (free) | `ubuntu-latest-arm64` (public repos only) |

## Cost (per-minute pricing)
| Runner | Cost |
|---|---|
| Standard Linux/Windows | Included in plan |
| Standard macOS | Included in plan |
| ARM64 public repos | Free |
| GPU (T4) | $0.07/min |
| M2 Pro xlarge | $0.16/min |
