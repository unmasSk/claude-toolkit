#!/usr/bin/env bash

# Transcribes audio to text using whisper.cpp. Accepts either a local audio file
# or a URL (YouTube or other yt-dlp-supported sites). Local audio files are
# converted to MP3 via ffmpeg; URLs are downloaded and extracted as MP3 via yt-dlp.
# In both cases, whisper-cli produces .txt and .vtt transcription files.
# Usage: ./transcribe.sh <audio-file-or-url>

set -euo pipefail

# --- CONFIG ---
# Prefer whisper-cli on PATH; fall back to common build locations
PGM=$(which whisper-cli 2>/dev/null || true)

if [[ -z "$PGM" ]]; then
    # Common build-from-source locations
    for candidate in \
        "${HOME}/whisper.cpp/build/bin/whisper-cli" \
        "/usr/local/bin/whisper-cli" \
        "/opt/homebrew/bin/whisper-cli"; do
        if [[ -x "$candidate" ]]; then
            PGM="$candidate"
            break
        fi
    done
fi

if [[ -z "$PGM" ]]; then
    echo "Error: whisper-cli not found." >&2
    echo "Install via: brew install whisper-cpp" >&2
    echo "Or build from source: https://github.com/ggerganov/whisper.cpp" >&2
    exit 1
fi

# Model: use WHISPER_MODEL env var, then fall back to common locations
if [[ -n "${WHISPER_MODEL:-}" && -f "${WHISPER_MODEL}" ]]; then
    MODEL="${WHISPER_MODEL}"
else
    # Infer model directory from PGM location and try common model names
    WHISPER_DIR="$(dirname "$(dirname "$(dirname "$PGM")")")"
    MODEL=""
    for candidate in \
        "${WHISPER_DIR}/models/ggml-medium.en.bin" \
        "${WHISPER_DIR}/models/ggml-base.en.bin" \
        "${WHISPER_DIR}/models/ggml-small.en.bin" \
        "${HOME}/.local/share/whisper/ggml-medium.en.bin" \
        "/usr/local/share/whisper/ggml-medium.en.bin"; do
        if [[ -f "$candidate" ]]; then
            MODEL="$candidate"
            break
        fi
    done
fi

if [[ -z "$MODEL" ]]; then
    echo "Error: No whisper model found." >&2
    echo "Set WHISPER_MODEL=/path/to/ggml-medium.en.bin or place a model in the whisper.cpp/models/ directory." >&2
    exit 1
fi

# --- FUNCTIONS ---
convert_audio_to_mp3() {
    local RAW=$1
    local MP3="${RAW%.*}.mp3"

    if [[ -e "${MP3}" ]]; then
        echo "========================================" >&2
        echo "Audio file already exists: ${MP3}" >&2
        echo "========================================" >&2
        echo "" >&2
        echo "${MP3}"
        return
    fi

    ffmpeg -i "${RAW}" -codec:a libmp3lame -q:a 0 "${MP3}" >&2
    echo "${MP3}"
}

download_and_extract_audio() {
    local URL=$1

    yt-dlp \
        --extractor-args "youtube:player-client=android" \
        --no-playlist \
        --restrict-filenames \
        -o "%(title).80s.%(ext)s" \
        --extract-audio \
        --audio-format mp3 \
        --audio-quality 0 \
        "$URL"
}

transcribe_audio() {
    local MP3=$1
    local BASENAME="${MP3%.mp3}"

    echo
    echo "================================================="
    echo "[$(date +"%Y%m%d.%H%M%S")] Transcribing: ${MP3}"
    echo "================================================="
    echo

    "${PGM}" \
        --output-txt \
        --output-vtt \
        --output-file "${BASENAME}" \
        --model "${MODEL}" \
        "${MP3}"

    # Remove empty lines from .vtt to reduce token usage during analysis
    # Cross-platform: use a temp file instead of sed -i '' (macOS-only)
    local VTT="${BASENAME}.vtt"
    local TMP="${VTT}.tmp"
    grep -v '^$' "${VTT}" > "${TMP}" && mv "${TMP}" "${VTT}"

    echo "Done: ${BASENAME}.txt and ${BASENAME}.vtt"
}

# --- MAIN ---
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <audio-file-or-url>"
    exit 1
fi

INPUT=$1

if [[ "$INPUT" == http://* || "$INPUT" == https://* ]]; then
    # URL input: download via yt-dlp, then transcribe
    if [[ "$INPUT" == *.mp3 ]]; then
        MP3="$INPUT"
    else
        # Record files before download to identify new file
        BEFORE_FILES=$(ls *.mp3 2>/dev/null || true)
        download_and_extract_audio "$INPUT"
        # Find the newly created mp3 (not in the before list)
        MP3=""
        for f in *.mp3; do
            if [[ -f "$f" ]] && ! echo "$BEFORE_FILES" | grep -qF "$f"; then
                MP3="$f"
                break
            fi
        done
        # Fallback: most recent mp3 if diff detection fails
        if [[ -z "$MP3" ]]; then
            MP3=$(ls -t *.mp3 2>/dev/null | head -1)
        fi
    fi

    if [[ -z "$MP3" ]]; then
        echo "Error: No MP3 file found."
        exit 1
    fi

    NEW_MP3=$(sed -E 's/\.+\.mp3$/.mp3/' <<< "$MP3")

    if [[ "$MP3" != "$NEW_MP3" ]]; then
        mv -f "$MP3" "$NEW_MP3"
    fi

    MP3="$NEW_MP3"

    if [[ ! -e "${MP3}" ]]; then
        echo "File not found: ${MP3}"
        exit 1
    fi
else
    # Local file input: convert to MP3, then transcribe
    if [[ ! -e "${INPUT}" ]]; then
        echo "File not found: ${INPUT}"
        exit 1
    fi

    MP3=$(convert_audio_to_mp3 "${INPUT}")
fi

transcribe_audio "$MP3"
