---
name: media-ffmpeg
description: >
  Use when the user asks to "trim video", "concat videos", "extract audio",
  "compress video", "convert video", "video conversion", "convertir video",
  "comprimir video", "recortar video", "concatenar videos", "extraer audio",
  or mentions any of: ffmpeg, ffprobe, video processing, audio extraction,
  codec, ProRes, H.264, H.265, format conversion, re-encode, scale video,
  fade, color correction, hardware acceleration, VideoToolbox, NVENC.
  Covers trimming, concatenation, format conversion, resolution scaling,
  audio operations, video effects, codec selection, and hardware acceleration.
version: 1.0.0
---

# FFmpeg -- Video and Audio Processing

Production-ready video and audio manipulation using FFmpeg and ffprobe.

## Routing Table

| Task | Load Reference |
|------|----------------|
| Trim, concat, convert, scale, audio ops, effects | `references/commands.md` |
| Codec selection, ProRes profiles, hardware acceleration | `references/codec-guide.md` |

Load references on-demand. Do not load both unless the task spans multiple domains.

## Capabilities

- Trim and cut clips (stream copy or frame-accurate re-encode)
- Concatenate clips (same-codec demuxer or cross-codec filter)
- Convert between formats (web, ProRes/FCP, archive/lossless)
- Scale and resize with aspect ratio preservation
- Audio: volume, normalize, mix tracks, replace audio
- Video effects: fade, speed, text overlay, color correction
- Validate output with ffprobe

## Workflow

1. **Inspect** -- Run `ffprobe` on the input. Verify codec, resolution, duration, and stream count before issuing any ffmpeg command.
2. **Process** -- Select the command from `references/commands.md`. Match codec strategy to the task (copy vs. re-encode).
3. **Verify** -- Run `ffprobe` on the output. Confirm expected codec, duration, and stream integrity.

## Mandatory Rules

- Always run `ffprobe` on the input before processing. Never issue an ffmpeg command blind.
- Prefer `-c copy` (stream copy) when no re-encode is needed -- it is fast and lossless. Use re-encoding only when codec conversion, scaling, or filter application requires it.
- For ProRes output targeting Final Cut Pro, always use `prores_ks` with `pcm_s16le` audio and `.mov` container.
- For web output, default to `libx264 -crf 23 -preset medium` with `aac` audio and `.mp4` container unless the user specifies otherwise.

## Done Criteria

A task is complete when:
- ffprobe confirms the output has the expected codec, resolution, and duration
- No ffmpeg errors or warnings in stderr that indicate data loss or codec mismatch
- Output file size is plausible relative to duration and codec
