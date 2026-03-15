# Image Edit Operations

Four supported operations. Each maps to a hardcoded fal.ai model.

## style — Style Transfer

Apply an artistic style or visual transformation to an image.

**Model:** `fal-ai/flux/dev/image-to-image`

**Parameters:**
- `--image-url` (required) — source image
- `--prompt` (required) — style description
- `--strength` (optional, default 0.75) — 0.3-0.5 subtle, 0.7-0.9 dramatic

**Example:**
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/media-image-edit/scripts/edit-image.sh \
  --image-url "https://example.com/photo.jpg" \
  --prompt "Convert to anime style" \
  --operation style \
  --strength 0.8
```

**When to use:** Artistic conversions, mood changes, visual style remapping.

---

## remove — Object Removal

Erase an object from the image. Can work without a mask for clearly described objects.

**Model:** `bria/eraser`

**Parameters:**
- `--image-url` (required)
- `--prompt` (required) — describe the object to remove
- `--mask-url` (optional) — binary mask for precise removal

**Example:**
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/media-image-edit/scripts/edit-image.sh \
  --image-url "https://example.com/photo.jpg" \
  --prompt "Remove the person on the left" \
  --operation remove
```

**Troubleshooting:** If object is not fully removed, be more specific in the prompt
or provide an explicit mask and use `inpaint` for precise control.

---

## background — Background Replacement

Replace or change the background while preserving the subject.

**Model:** `fal-ai/flux-pro/kontext`

**Parameters:**
- `--image-url` (required)
- `--prompt` (required) — describe the new background

**Example:**
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/media-image-edit/scripts/edit-image.sh \
  --image-url "https://example.com/portrait.jpg" \
  --prompt "Place in a tropical beach setting" \
  --operation background
```

**Troubleshooting:** If artifacts appear around the subject edges, use a cleaner
source image or adjust `--strength`.

---

## inpaint — Inpainting

Fill or replace a masked area of the image with generated content.

**Model:** `fal-ai/flux-lora-fill`

**Parameters:**
- `--image-url` (required)
- `--mask-url` (required) — binary mask: white = edit area, black = preserve
- `--prompt` (required) — describe what to generate in the masked area

**Example:**
```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/media-image-edit/scripts/edit-image.sh \
  --image-url "https://example.com/photo.jpg" \
  --mask-url "https://example.com/mask.png" \
  --prompt "Fill with flowers" \
  --operation inpaint
```

**Mask format:** PNG with solid white/black or transparency. Feathered edges
produce smoother transitions. White pixels are edited; black pixels are preserved.

---

## Strength Tuning (style only)

| Value | Effect |
|---|---|
| 0.3-0.5 | Subtle — preserves most of original |
| 0.6-0.75 | Balanced (default 0.75) |
| 0.8-1.0 | Dramatic — strong transformation |
