# FFmpeg Command Patterns

Production-ready FFmpeg commands for common video and audio operations.

## Video Information

```bash
# Get full metadata
ffprobe -v quiet -print_format json -show_format -show_streams "input.mp4"

# Get duration only
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "input.mp4"

# Get resolution
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "input.mp4"
```

## Trimming and Cutting

```bash
# Trim by time (fast, no re-encoding)
ffmpeg -ss 00:01:30 -i input.mp4 -to 00:02:45 -c copy output.mp4

# Trim with re-encoding (frame-accurate)
ffmpeg -ss 00:01:30 -i input.mp4 -to 00:02:45 -c:v libx264 -c:a aac output.mp4

# Extract specific segment by frames
ffmpeg -i input.mp4 -vf "select=between(n\,100\,500)" -vsync vfr output.mp4
```

## Concatenation

```bash
# Using concat demuxer (same codecs required)
# First create file list:
# file 'clip1.mp4'
# file 'clip2.mp4'
# file 'clip3.mp4'

ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4

# Using concat filter (different codecs, re-encodes)
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1" output.mp4
```

## Format Conversion

```bash
# MP4 to MOV (ProRes for FCP)
ffmpeg -i input.mp4 -c:v prores_ks -profile:v 3 -c:a pcm_s16le output.mov

# Any to H.264 MP4 (web-friendly)
ffmpeg -i input.avi -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output.mp4

# Extract audio only
ffmpeg -i video.mp4 -vn -c:a libmp3lame -q:a 2 audio.mp3
ffmpeg -i video.mp4 -vn -c:a pcm_s16le audio.wav
```

## Resolution and Scaling

```bash
# Scale to specific resolution
ffmpeg -i input.mp4 -vf "scale=1920:1080" output.mp4

# Scale maintaining aspect ratio
ffmpeg -i input.mp4 -vf "scale=1920:-1" output.mp4

# Scale to fit within bounds
ffmpeg -i input.mp4 -vf "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease" output.mp4
```

## Audio Operations

```bash
# Adjust volume
ffmpeg -i input.mp4 -af "volume=1.5" output.mp4

# Normalize audio (loudnorm) — single-pass (good for most use cases)
ffmpeg -i input.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11 output.mp4

# Normalize audio — two-pass (broadcast-accurate)
# Pass 1: measure loudness stats (outputs to stderr)
ffmpeg -i input.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null /dev/null
# Pass 2: apply measured values (replace MEASURED_* with values from pass 1 output)
ffmpeg -i input.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=MEASURED_I:measured_LRA=MEASURED_LRA:measured_TP=MEASURED_TP:measured_thresh=MEASURED_THRESH:linear=true output.mp4

# Mix audio tracks
ffmpeg -i video.mp4 -i audio.mp3 -filter_complex "[0:a][1:a]amerge=inputs=2[aout]" -map 0:v:0 -map "[aout]" -c:v copy output.mp4

# Replace audio
ffmpeg -i video.mp4 -i new_audio.mp3 -c:v copy -map 0:v:0 -map 1:a:0 output.mp4
```

## Video Effects and Filters

```bash
# Fade in/out
ffmpeg -i input.mp4 -vf "fade=t=in:st=0:d=1,fade=t=out:st=9:d=1" output.mp4

# Speed adjustment (2x faster)
ffmpeg -i input.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" output.mp4

# Add text overlay
ffmpeg -i input.mp4 -vf "drawtext=text='Title':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=50" output.mp4

# Color correction
ffmpeg -i input.mp4 -vf "eq=brightness=0.1:saturation=1.2:contrast=1.1" output.mp4
```

## Error Handling

```bash
# Check if file is valid video
ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "file.mp4" 2>/dev/null
# Returns "video" if valid

# Validate output after processing
validate_video() {
  local file="$1"
  if ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$file" 2>/dev/null | grep -q "video"; then
    echo "Valid"
    return 0
  else
    echo "Invalid or missing video stream"
    return 1
  fi
}
```
