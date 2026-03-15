---
name: media-transcribe
description: >
  Use when the user wants to transcribe or analyze audio or video content.
  Triggers: "transcribe", "transcription", "whisper", "yt-dlp",
  "download youtube audio", "transcribir", "transcripción",
  or when the user provides a URL (YouTube, TikTok, Instagram, Twitter/X)
  or a local audio/video file (.m4a, .mp3, .wav, .ogg, .flac, .aac, .wma)
  or an existing .vtt file for analysis.
  Covers: audio download via yt-dlp, transcription via whisper.cpp,
  and structured critical analysis of the resulting transcript.
version: 1.0.0
---

# media-transcribe -- Audio/Video Transcription and Analysis

Transcribe audio or video content and produce a structured critical analysis.
Priority order for transcription source: existing subtitles → auto-subtitles → whisper.

## Request Routing

| Input Type | Action | Reference |
|---|---|---|
| `.vtt` file | Skip to Analysis step | `references/analysis-prompt.md` |
| Audio file (`.m4a`, `.mp3`, `.wav`, `.ogg`, `.flac`, `.aac`, `.wma`) | Run transcribe script | `references/analysis-prompt.md` |
| URL (YouTube, TikTok, Instagram, Twitter/X) | Run transcribe script | `references/platforms.md`, `references/analysis-prompt.md` |
| Whisper model selection needed | Consult model guide | `references/whisper-models.md` |

## Workflow

### Step 1 -- Detect Input

Inspect `$ARGUMENTS`:

- Starts with `http://` or `https://` → URL path (Step 2a)
- Ends with `.vtt` → skip to Step 3
- Otherwise → local audio file (Step 2b)

For URLs, check `references/platforms.md` for platform-specific notes and subtitle availability.

### Step 2a -- Download from URL

**Before running whisper**, check whether the platform already provides subtitles — this saves download time and often produces better results. Load `references/platforms.md` for platform-specific subtitle availability. For YouTube, try `yt-dlp --list-subs <url>` first. If subtitles exist, download them with `yt-dlp --write-subs --skip-download <url>` and skip directly to Step 3 (Analysis). The transcribe.sh script does NOT perform this check automatically — it always downloads audio and runs whisper. This optimization is the agent's responsibility.

Run the transcription script (only if no subtitles are available):

```
${CLAUDE_PLUGIN_ROOT}/skills/media-transcribe/scripts/transcribe.sh "<url>"
```

The script downloads audio via yt-dlp and produces a `.vtt` file in the current directory. Find the most recently created `.vtt` file.

### Step 2b -- Transcribe Local Audio

Run the transcription script:

```
${CLAUDE_PLUGIN_ROOT}/skills/media-transcribe/scripts/transcribe.sh "<audio-file>"
```

The script converts the file to MP3 via ffmpeg and produces a `.vtt` file with the same base name.

### Step 3 -- Analyze Transcript

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/media-transcribe/references/analysis-prompt.md`.
2. Infer a human-readable title from the `.vtt` filename.
3. Replace `[TITLE]` with the inferred title and `[SOURCE]` with the original `$ARGUMENTS` value.
4. Read the **entire** `.vtt` file before writing a single word of analysis. Use `offset` and `limit` parameters for large files.
5. Check whether a `.md` output file already exists (same base name as `.vtt`). If it does, ask the user: overwrite or rename?
6. Write the analysis to the `.md` output file in the same directory as the `.vtt` file.

## whisper-cli Discovery

The script performs PATH lookup automatically. If `whisper-cli` is not found on PATH, the script exits with an error. Install options:

```bash
# macOS (Homebrew)
brew install whisper-cpp

# Build from source
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp && cmake -B build && cmake --build build -j
```

Model path is resolved via the `WHISPER_MODEL` environment variable. If not set, the script falls back to common locations. See `references/whisper-models.md` for model selection.

## Mandatory Rules

- NEVER begin analysis before reading the full `.vtt` file.
- NEVER hardcode paths — all paths use `${CLAUDE_PLUGIN_ROOT}` or PATH lookup.
- Timestamps in analysis: `[HH:MM:SS]` for points, `[HH:MM:SS--HH:MM:SS]` for ranges (double hyphen, not en-dash).
- Maintain neutral, descriptive tone — do not endorse or criticize speaker views.
- Output `.md` file goes in the same directory as the `.vtt` file.

## Done Criteria

- [ ] `.vtt` file exists and has been fully read
- [ ] Analysis written following `references/analysis-prompt.md` structure exactly
- [ ] All timestamps correctly formatted
- [ ] Output `.md` file saved to correct location
