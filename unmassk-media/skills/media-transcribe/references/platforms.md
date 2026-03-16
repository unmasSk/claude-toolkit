# Supported Platforms

Transcription source priority for every platform:
1. Existing manual subtitles (highest accuracy, zero cost)
2. Auto-generated subtitles from the platform
3. Whisper transcription from downloaded audio (fallback)

## Platform Reference

| Platform | yt-dlp Support | Manual Subtitles | Auto-Subtitles | Notes |
|---|---|---|---|---|
| YouTube | Full | Yes (many videos) | Yes (most videos) | Best coverage. Try `--write-subs --write-auto-subs` before whisper. |
| TikTok | Full | Rare | Rare | Most TikTok content requires whisper. Audio quality varies. |
| Instagram | Partial | No | No | Reels and posts supported; Stories may fail. Requires whisper. |
| Twitter / X | Full | No | No | Video tweets supported. Requires whisper. Authentication may be needed for private/age-gated content. |
| Local files | N/A | N/A | N/A | Any format ffmpeg supports. Converted to MP3 before whisper. |

## Subtitle Download (Skip Whisper When Available)

For YouTube, check for subtitles before running whisper — it saves time and produces better output:

```bash
# List available subtitle tracks
yt-dlp --list-subs "<url>"

# Download manual subtitles (preferred)
yt-dlp --write-subs --sub-lang en --skip-download -o "%(title).80s.%(ext)s" "<url>"

# Download auto-generated subtitles (fallback)
yt-dlp --write-auto-subs --sub-lang en --skip-download -o "%(title).80s.%(ext)s" "<url>"
```

Downloaded subtitle files are `.vtt` — pass them directly to the analysis step.

## Known Limitations

- **Instagram**: Private accounts and Stories are unreliable. yt-dlp may require a cookies file (`--cookies-from-browser chrome`).
- **Twitter/X**: Age-gated or account-restricted content requires authentication (`--cookies-from-browser`).
- **TikTok**: File naming from yt-dlp can include non-ASCII characters — `--restrict-filenames` handles this.
- **Long videos (>2h)**: Whisper processing time scales linearly with duration. Use `medium` or smaller model for faster turnaround.
