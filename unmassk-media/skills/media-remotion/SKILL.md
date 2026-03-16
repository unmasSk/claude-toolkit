---
name: media-remotion
description: >
  Use when the user is working with Remotion — video creation in React.
  Trigger phrases: "create a video", "render a video", "Remotion composition",
  "animate in Remotion", "Remotion component", "video with React",
  "add audio to video", "add captions", "add subtitles", "transcribe audio",
  "audio visualization", "spectrum bars", "waveform animation",
  "sound effects in video", "FFmpeg in Remotion", "trim video", "loop video",
  "transparent video", "Lottie in video", "GIF in video", "map animation",
  "chart animation", "bar chart video", "text animation video",
  "typewriter effect", "word highlight", "voiceover", "ElevenLabs TTS",
  "spring animation", "interpolate", "useCurrentFrame", "useVideoConfig",
  "Sequence", "TransitionSeries", "calculateMetadata", "Zod schema video",
  "Mapbox animation", "Three.js Remotion", "React Three Fiber video",
  "TailwindCSS Remotion", "Google Fonts Remotion", "measureText Remotion",
  "Mediabunny", "video dimensions", "video duration", "audio duration",
  or mentions any of: Remotion, @remotion, renderMedia, renderStill,
  useCurrentFrame, useVideoConfig, Composition, Sequence, AbsoluteFill,
  TransitionSeries, staticFile, calculateMetadata.
  Covers animations, audio, captions, charts, 3D, transitions, fonts, images,
  GIFs, Lottie, maps, parameters, sequencing, text animations, timing, trimming,
  transparent video, and FFmpeg operations within Remotion projects.
  Based on @remotion/skills by Remotion Inc. (MIT License).
version: 1.0.0
---

# Remotion — Video Creation in React

Domain-specific knowledge for building Remotion video compositions. Load
reference files on-demand based on user intent — do not load all at startup.

## Request Routing

| User Request | Load Reference |
|---|---|
| 3D content, Three.js, React Three Fiber | `references/3d.md` |
| Animations, useCurrentFrame, basic motion | `references/animations.md` |
| Importing assets, staticFile, public folder | `references/assets.md` |
| Audio visualization, spectrum bars, waveforms | `references/audio-visualization.md` |
| Audio playback, volume, speed, pitch, loop | `references/audio.md` |
| Dynamic duration/dimensions, calculateMetadata | `references/calculate-metadata.md` |
| Video decode compatibility check, Mediabunny | `references/can-decode.md` |
| Charts, bar/pie/line/stock graphs | `references/charts.md` + `references/assets/charts-bar-chart.tsx` |
| Defining compositions, stills, fps, duration | `references/compositions.md` |
| Displaying captions, TikTok-style subtitles | `references/display-captions.md` |
| Extract video frames, thumbnails, Mediabunny | `references/extract-frames.md` |
| FFmpeg, FFprobe, video trimming via CLI | `references/ffmpeg.md` |
| Google Fonts, local fonts, typography | `references/fonts.md` |
| Audio file duration, Mediabunny | `references/get-audio-duration.md` |
| Video file width/height, Mediabunny | `references/get-video-dimensions.md` |
| Video file duration, Mediabunny | `references/get-video-duration.md` |
| GIFs, APNG, AVIF, WebP animated images | `references/gifs.md` |
| Static images, Img component | `references/images.md` |
| Import .srt subtitle files | `references/import-srt-captions.md` |
| Light leak overlays, @remotion/light-leaks | `references/light-leaks.md` |
| Lottie animations | `references/lottie.md` |
| Mapbox map animations | `references/maps.md` |
| Measuring DOM nodes, getBoundingClientRect | `references/measuring-dom-nodes.md` |
| Measuring text, fitText, fillTextBox | `references/measuring-text.md` |
| Zod schema, video parameters, props | `references/parameters.md` |
| Sequencing, delay, trim, Sequence component | `references/sequencing.md` |
| Sound effects, audio tag, sfx | `references/sfx.md` |
| Captions format, Caption type, JSON subtitles | `references/subtitles.md` |
| TailwindCSS in Remotion | `references/tailwind.md` |
| Text animations, typewriter, word highlight | `references/text-animations.md` + `references/assets/text-animations-typewriter.tsx` + `references/assets/text-animations-word-highlight.tsx` |
| Interpolation, easing, spring animations | `references/timing.md` |
| Transcribing audio, Whisper, speech-to-text | `references/transcribe-captions.md` |
| Scene transitions, TransitionSeries, fade/slide | `references/transitions.md` |
| Transparent video, alpha channel, VP9, ProRes | `references/transparent-videos.md` |
| Trimming animations, clip start/end | `references/trimming.md` |
| Embedding videos, OffthreadVideo, loop, speed | `references/videos.md` |
| AI voiceover, ElevenLabs TTS | `references/voiceover.md` |
