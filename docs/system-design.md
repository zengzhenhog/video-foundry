# video-foundry Video Production System Design

Version: 0.1  
Date: 2026-05-19  
Target directory: `F:\code\auto-image`  
Status: Draft for implementation planning

## 1. Overview

This document defines a semi-automated production system that turns official high-resolution James Webb Space Telescope images and official textual descriptions into narrated short videos.

The system is designed around one hard requirement: image fidelity. AI may generate scripts, narration text, translations, metadata summaries, and speech audio, but it must not generate, redraw, extend, hallucinate, or visually alter the astronomical image content. All video motion is produced by deterministic camera movement over the original image pixels plus optional non-destructive overlays such as subtitles, credits, and light particle layers.

The recommended implementation uses a Python-first programmatic rendering pipeline. Python coordinates source ingestion, script generation, voice generation, frame rendering, review, and export. FFmpeg is used for final encoding and audio/video assembly.

## 2. Goals

- Import official Webb images, source descriptions, credits, and metadata.
- Generate Chinese narration scripts based only on official source text.
- Create storyboard and shot plans for slow push-in, pan, local zoom, hold, and pull-back shots.
- Render faithful image-based videos without AI-generated visual modification.
- Generate AI narration using configurable or custom voices.
- Produce subtitles, end credits, and multiple output formats such as 9:16 and 16:9.
- Provide a human review step before final export or publishing.
- Preserve provenance: source URL, credit, original image file, generated script, storyboard JSON, voice configuration, and render logs.

## 3. Non-Goals

- No image-to-video generative model in the MVP.
- No AI upscaling, AI inpainting, AI outpainting, AI denoising, or AI style transfer.
- No automatic publishing in the first version.
- No scientific claim generation beyond the official source description.
- No real-time video editor in the MVP. The review UI can be simple and task-oriented.

## 4. System Constraints

### 4.1 Image Fidelity

The renderer must treat the official image as immutable input. Motion is created by changing a crop rectangle over time:

- `crop_start` defines the initial camera window.
- `crop_end` defines the final camera window.
- The renderer interpolates the crop rectangle frame by frame.
- The crop is scaled to the target canvas.
- Overlays are composited above the result.

The pipeline must keep the original image unchanged at `assets/original.*`.

### 4.2 Scientific Reliability

Generated narration must be grounded in official descriptions. The LLM prompt must require:

- No unsupported distances, dates, object types, or causal claims.
- No invented telescope settings or observation details.
- Explicit uncertainty where the source text is uncertain.
- A short source note for internal review.

### 4.3 Copyright and Attribution

Each video project must store and render visible credit text. NASA material is generally usable under NASA media guidelines, but the system must not imply NASA endorsement. ESA/Webb material commonly requires visible credit. Credits should appear in the video outro and optionally in small on-screen text.

Recommended source references:

- NASA Webb image gallery: https://science.nasa.gov/mission/webb/multimedia/images/
- NASA Images API docs: https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf
- NASA media guidelines: https://www.nasa.gov/nasa-brand-center/images-and-media/
- ESA/Webb copyright and usage: https://esawebb.org/copyright/

## 5. Recommended Architecture

```text
Source Import
  -> Asset Normalization
  -> Script Generation
  -> Storyboard Planning
  -> Voice Generation
  -> Subtitle Generation
  -> Programmatic Rendering
  -> FFmpeg Assembly
  -> Human Review
  -> Export
```

The system should be built as a local-first service at first. It can later be moved to a server or cloud worker architecture.

## 6. Components

### 6.1 Asset Collector

Responsibilities:

- Accept manual input: image URL, description text, credit, title, source URL.
- Optionally search official sources through the NASA Image and Video Library API.
- Download the highest available image asset.
- Save normalized metadata to `asset.json`.
- Validate that required attribution fields are present.

NASA Images API endpoints useful for automation:

- `/search`
- `/asset/{nasa_id}`
- `/metadata/{nasa_id}`
- `/captions/{nasa_id}`

### 6.2 Asset Normalizer

Responsibilities:

- Store original image in a project folder.
- Extract width, height, aspect ratio, file type, and color profile.
- Create preview thumbnails for review UI.
- Reject images below a configurable resolution threshold.
- Preserve source metadata and credit exactly as provided.

Output files:

```text
projects/{project_id}/assets/original.jpg
projects/{project_id}/assets/preview.jpg
projects/{project_id}/metadata/asset.json
```

### 6.3 Script Generator

Responsibilities:

- Generate narration text from official description.
- Support duration targets: 30, 45, 60, 90 seconds.
- Generate title, hook, body, ending, and optional short caption.
- Generate an internal source-grounding summary for review.

Inputs:

- Official title
- Official description
- Credit
- Target language
- Target duration
- Audience level

Outputs:

```text
projects/{project_id}/script/script.md
projects/{project_id}/script/script.json
```

Example script JSON:

```json
{
  "language": "zh-CN",
  "duration_target_sec": 60,
  "title": "韦伯望远镜看到的恒星诞生区",
  "narration": "这张图像来自詹姆斯·韦伯太空望远镜...",
  "review_notes": ["All claims are derived from the official source description.", "No distance value was added because the source text did not include one."]
}
```

### 6.4 Storyboard Planner

Responsibilities:

- Convert narration into timed shots.
- Generate crop-based camera movements.
- Avoid extreme zoom when the source resolution is insufficient.
- Keep subtitles synchronized with narration sections.
- Add a final credit shot.

Supported shot types for MVP:

- `slow_push_in`
- `pan_left`
- `pan_right`
- `pan_up`
- `pan_down`
- `local_zoom`
- `hold`
- `pull_back`
- `crossfade_to_credit`

Shot plan example:

```json
{
  "format": "9:16",
  "fps": 30,
  "duration_sec": 60,
  "shots": [
    {
      "id": "shot_001",
      "start_sec": 0,
      "end_sec": 7.5,
      "type": "slow_push_in",
      "crop_start": [0.05, 0.05, 0.9, 0.9],
      "crop_end": [0.15, 0.12, 0.7, 0.7],
      "easing": "easeInOutCubic",
      "caption": "这张图像来自詹姆斯·韦伯太空望远镜。"
    }
  ]
}
```

Crop values are normalized as `[x, y, width, height]`, where `0.0` to `1.0` maps to the original image dimensions.

### 6.5 Render Engine

Recommended primary renderer: a Python render engine using Pillow/OpenCV for deterministic frame generation, with FFmpeg for video encoding. MoviePy can be used as a helper for timeline assembly, but the core image motion logic should remain explicit and testable in Python.

Responsibilities:

- Render video frames from original image crop windows.
- Add subtitles, credit overlays, optional particle layers, and background gradients outside image bounds if needed.
- Export intermediate silent video.
- Support target formats:
  - `1080x1920` vertical
  - `1920x1080` horizontal
  - `1080x1080` square

Allowed visual operations:

- Crop
- Scale
- Translate
- Rotate slightly, within conservative limits
- Fade in/out
- Add subtitles
- Add credit text
- Add non-destructive particle overlay
- Add letterbox or blurred background derived from the same image only if explicitly enabled

Disallowed visual operations:

- Generative image modification
- AI inpainting or outpainting
- AI video interpolation that invents details
- AI upscaling that changes visible structure
- Object removal or replacement
- Color remapping that changes scientific appearance unless configured as a clearly decorative background layer

### 6.6 Particle Overlay

Particle effects should be subtle and clearly decorative. They must not imply actual stars, galaxies, or observed structures in the Webb image.

MVP particle layer:

- Python-generated point particles using Pillow/OpenCV, or a pre-rendered transparent overlay sequence.
- Low opacity.
- Slow drift.
- Rendered above or outside the main image.
- Disabled by default for scientifically sensitive videos.

### 6.7 Voice Engine

Responsibilities:

- Generate narration audio from approved script.
- Support custom voice IDs.
- Save voice provider, voice ID, settings, and generated audio.
- Return word or sentence timing when available.

Recommended providers:

- ElevenLabs for creator workflows and custom voice cloning.
- Azure AI Speech Custom Neural Voice for enterprise-grade custom voices with formal consent and deployment controls.
- OpenAI text-to-speech for simple built-in voices when custom cloning is not required.

Output files:

```text
projects/{project_id}/audio/narration.wav
projects/{project_id}/audio/narration.mp3
projects/{project_id}/audio/voice.json
```

### 6.8 Subtitle Generator

Responsibilities:

- Generate SRT and WebVTT subtitles.
- Prefer TTS timestamps if the provider returns them.
- Fall back to speech-to-text alignment if needed.
- Enforce line length and safe-area constraints for vertical video.

Output files:

```text
projects/{project_id}/subtitles/subtitles.srt
projects/{project_id}/subtitles/subtitles.vtt
```

### 6.9 Assembler

Responsibilities:

- Combine silent video, narration, optional background music, and subtitles.
- Normalize audio loudness.
- Add outro credit section.
- Export final MP4 files.

Recommended tool: FFmpeg.

Output files:

```text
projects/{project_id}/exports/final_9x16.mp4
projects/{project_id}/exports/final_16x9.mp4
projects/{project_id}/exports/final_1x1.mp4
```

### 6.10 Review UI

Responsibilities:

- Show original image and metadata.
- Show generated script.
- Show storyboard shots and crop rectangles overlaid on the original image.
- Show narration audio preview.
- Show rendered video preview.
- Allow user actions:
  - approve script
  - regenerate script
  - edit script
  - approve storyboard
  - adjust crop rectangles
  - approve final export

The review UI does not need to be a full editor. It only needs enough control to catch scientific, attribution, and framing problems.

## 7. Project Directory Layout

```text
auto-image/
  docs/
    system-design.md
  src/
    auto_image/
      api/
      review_ui/
      renderer/
      storyboard/
      ffmpeg/
      voice/
      sources/
      shared/
  projects/
    {project_id}/
      assets/
      metadata/
      script/
      storyboard/
      audio/
      subtitles/
      renders/
      exports/
      logs/
  config/
    voices.example.json
    render-presets.json
    providers.example.env
  tests/
    unit/
    integration/
```

## 8. Core Data Models

### 8.1 Asset

```json
{
  "id": "string",
  "title": "string",
  "source": "NASA | ESA | STScI | manual",
  "source_url": "string",
  "image_url": "string",
  "local_original_path": "string",
  "description": "string",
  "credit": "string",
  "published_at": "string",
  "width": 0,
  "height": 0,
  "license_notes": "string"
}
```

### 8.2 Production Job

```json
{
  "id": "string",
  "asset_id": "string",
  "status": "draft | script_ready | storyboard_ready | audio_ready | rendered | approved | exported | failed",
  "target_language": "zh-CN",
  "target_duration_sec": 60,
  "formats": ["9:16", "16:9"],
  "voice_id": "string",
  "created_at": "string",
  "updated_at": "string"
}
```

### 8.3 Storyboard

```json
{
  "version": 1,
  "fps": 30,
  "duration_sec": 60,
  "safe_area": {
    "top": 0.08,
    "bottom": 0.12,
    "left": 0.06,
    "right": 0.06
  },
  "shots": []
}
```

## 9. Workflow

### 9.1 Manual-Assisted MVP Workflow

1. User creates a project and pastes official image URL, description, and credit.
2. System downloads the image and validates metadata.
3. User selects duration, output format, and voice.
4. LLM generates script.
5. User reviews and approves script.
6. System generates storyboard JSON.
7. User reviews crop rectangles and shot timing.
8. TTS generates narration audio.
9. System renders silent video from original image.
10. FFmpeg assembles final video.
11. User reviews final export.
12. System writes final MP4, SRT, source metadata, and credits.

### 9.2 Future Automated Workflow

1. System searches official image APIs by keyword.
2. Candidate assets enter an import queue.
3. Low-quality or missing-credit assets are rejected.
4. Scripts and storyboards are generated in batch.
5. User reviews only selected candidates.
6. Approved jobs render in background workers.

## 10. API Surface

Initial REST endpoints:

```text
POST /projects
GET  /projects/{id}
POST /projects/{id}/import
POST /projects/{id}/generate-script
POST /projects/{id}/approve-script
POST /projects/{id}/generate-storyboard
POST /projects/{id}/approve-storyboard
POST /projects/{id}/generate-voice
POST /projects/{id}/render
POST /projects/{id}/export
GET  /projects/{id}/preview
GET  /projects/{id}/downloads
```

## 11. Configuration

### 11.1 Render Presets

```json
{
  "vertical_short": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "bitrate": "12M",
    "subtitle_style": "vertical_safe"
  },
  "horizontal_hd": {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "bitrate": "16M",
    "subtitle_style": "horizontal_safe"
  }
}
```

### 11.2 Voice Presets

```json
{
  "custom_narrator_cn": {
    "provider": "elevenlabs",
    "voice_id": "replace-with-real-id",
    "language": "zh-CN",
    "stability": 0.55,
    "similarity_boost": 0.75
  }
}
```

## 12. Error Handling

The system should fail fast for:

- Missing credit.
- Missing source URL.
- Image download failure.
- Image resolution below threshold.
- LLM output containing unsupported claims detected by validation.
- TTS generation failure.
- Python render engine or FFmpeg render failure.

Each failed job should write:

```text
projects/{project_id}/logs/error.json
projects/{project_id}/logs/pipeline.log
```

Error responses should include:

- Failed step
- Human-readable reason
- Retryable flag
- Suggested correction

## 13. Validation and Quality Gates

Before final export, the system must check:

- Original image exists and hash is recorded.
- Credit text is present.
- Source URL is present.
- Script has user approval.
- Storyboard has user approval.
- Each crop rectangle stays inside image bounds.
- Maximum zoom does not exceed configured threshold.
- Subtitle text stays inside safe area.
- Narration audio duration roughly matches storyboard duration.
- Final video includes visible credit.

Recommended output report:

```text
projects/{project_id}/exports/quality-report.json
```

## 14. Security and Secrets

API keys must not be stored inside project metadata or committed files. Use environment variables or local secret files ignored by git:

```text
.env
config/providers.local.env
```

Secrets:

- LLM provider key
- TTS provider key
- Optional cloud storage key

User voice cloning must require explicit authorization. The system should store only provider voice IDs unless local voice files are truly required.

## 15. Testing Strategy

### 15.1 Unit Tests

- Crop rectangle validation.
- Duration and shot timing calculation.
- Subtitle line breaking.
- Credit presence validation.
- Script schema validation.
- Provider configuration parsing.

### 15.2 Integration Tests

- Import sample asset.
- Generate deterministic storyboard from fixed script.
- Render 5-second preview video.
- Assemble video with test audio.
- Export SRT and MP4.

### 15.3 Visual Regression Tests

- Render still frames from key timestamps.
- Compare dimensions, blank frame detection, and crop bounds.
- Verify no frame is fully black unless it is an intentional fade.

### 15.4 Manual Review

Manual review remains required for:

- Scientific wording.
- Credit correctness.
- Framing quality.
- Subtitle readability.
- Voice tone.

## 16. MVP Milestones

### Milestone 1: Local Pipeline

- Manual asset input.
- Image download and metadata storage.
- Script generation.
- Storyboard JSON generation.
- Basic Python frame rendering and FFmpeg encoding.
- Final MP4 with narration and subtitles.

### Milestone 2: Review UI

- Project list.
- Asset preview.
- Script editor.
- Shot crop preview.
- Render preview.
- Approval buttons.

### Milestone 3: Batch Production

- NASA Images API search.
- Job queue.
- Batch script generation.
- Batch rendering.
- Export management.

### Milestone 4: Production Hardening

- Provider retry logic.
- Quality reports.
- Cloud storage option.
- Team review roles.
- Publishing integrations.

## 17. Recommended Initial Build

Use a Python project structure:

- `src/auto_image/api`: FastAPI API service.
- `src/auto_image/review_ui`: simple review UI or server-rendered review pages.
- `src/auto_image/renderer`: Python frame renderer using Pillow/OpenCV.
- `src/auto_image/storyboard`: crop and shot planning logic.
- `src/auto_image/voice`: TTS provider adapters.
- `src/auto_image/ffmpeg`: FFmpeg command builders and assembly helpers.
- `src/auto_image/sources`: NASA and manual import logic.
- `src/auto_image/shared`: schemas, config loading, and shared types.

Use Pydantic or JSON Schema for all pipeline artifacts. This keeps generated LLM output constrained and reviewable.

Recommended MVP renderer choice: Python frame generation with Pillow/OpenCV, followed by FFmpeg for final video encoding and audio/video assembly.

## 18. Open Decisions

- Whether to use pure Python rendering only, or Python rendering plus MoviePy as a timeline helper.
- First TTS provider: ElevenLabs, Azure, or another provider.
- First LLM provider and model.
- Whether the first version should include a web review UI or start with CLI plus generated preview images.
- Whether NASA API search is included in MVP or added after manual import works.

## 19. Acceptance Criteria

The MVP is successful when a user can:

1. Create a project from one official Webb image and description.
2. Generate a Chinese narration script.
3. Review and approve the script.
4. Generate a crop-based storyboard.
5. Generate AI narration with a configured voice.
6. Render a 45-60 second video with subtitles and credit.
7. Export both vertical and horizontal MP4 files.
8. Verify that the astronomical image content was not AI-generated or visually modified.
