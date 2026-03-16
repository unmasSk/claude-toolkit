# Codec Selection Guide

## Codec by Use Case

| Use Case | Video Codec | Audio Codec | Container |
|----------|-------------|-------------|-----------|
| Web delivery | libx264/libx265 | aac | mp4 |
| Final Cut Pro | prores_ks | pcm_s16le | mov |
| Archive/lossless | ffv1 | flac | mkv |
| Quick preview | libx264 -preset ultrafast | aac | mp4 |
| Social media | libx264 -crf 20 | aac -b:a 192k | mp4 |

## ProRes Profiles (for FCP)

| Profile | Flag | Quality | Use Case |
|---------|------|---------|----------|
| Proxy | -profile:v 0 | Low | Offline editing |
| LT | -profile:v 1 | Medium | Light grading |
| Standard | -profile:v 2 | High | General editing |
| HQ | -profile:v 3 | Very High | Final delivery |
| 4444 | -profile:v 4 | Highest | VFX/compositing |

## H.265 (HEVC) Example

```bash
# H.265 encoding — ~50% smaller files than H.264 at same quality
# CRF 28 is the x265 equivalent of x264 CRF 23 (medium quality)
ffmpeg -i input.mp4 -c:v libx265 -crf 28 -preset medium -tag:v hvc1 -c:a aac output.mp4

# Note: -tag:v hvc1 is required for Apple/QuickTime compatibility
# Not all browsers support H.265 — use H.264 for maximum compatibility
```

## Hardware Acceleration

```bash
# macOS (VideoToolbox)
ffmpeg -hwaccel videotoolbox -i input.mp4 -c:v h264_videotoolbox output.mp4

# Linux with NVIDIA (CUDA)
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_nvenc output.mp4

# Parallel processing (use all available threads)
ffmpeg -i input.mp4 -threads 0 output.mp4

# Limit memory usage
ffmpeg -i input.mp4 -max_muxing_queue_size 1024 output.mp4
```

Check available hardware accelerators: `ffmpeg -hwaccels`
