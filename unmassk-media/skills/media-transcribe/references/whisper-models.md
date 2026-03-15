# Whisper Model Selection

whisper.cpp ships with several model sizes. Choose based on content length, required accuracy, and available hardware.

## Model Comparison

| Model | Size | VRAM | Speed (RTX 3080) | Accuracy | Best For |
|---|---|---|---|---|---|
| `tiny` | 75 MB | ~1 GB | ~32x realtime | Low | Quick tests, drafts, short clips |
| `base` | 142 MB | ~1 GB | ~16x realtime | Moderate | Short videos (<15 min), casual content |
| `small` | 466 MB | ~2 GB | ~6x realtime | Good | General use, podcasts |
| `medium` | 1.5 GB | ~5 GB | ~2x realtime | High | Default recommendation |
| `large` | 2.9 GB | ~10 GB | ~1x realtime | Highest | Academic, technical, non-English |

English-only variants (`*.en.bin`) are ~10-15% faster than multilingual models on English content with no accuracy loss.

## Recommendation

Start with `medium.en` for most use cases. Drop to `small.en` if processing time is a constraint. Use `large` only for:
- Non-English or heavily accented speech
- Technical jargon requiring maximum accuracy
- Content where timestamps must be precise

## Download Models

```bash
# From within the whisper.cpp directory
bash models/download-ggml-model.sh medium.en
bash models/download-ggml-model.sh large-v3

# Or download directly
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin \
  -P /path/to/whisper.cpp/models/
```

## Setting the Model Path

The script reads `WHISPER_MODEL` from the environment first:

```bash
export WHISPER_MODEL="/path/to/whisper.cpp/models/ggml-medium.en.bin"
```

If not set, the script searches common locations relative to the `whisper-cli` binary. Set `WHISPER_MODEL` explicitly in your shell profile to lock in a specific model.
