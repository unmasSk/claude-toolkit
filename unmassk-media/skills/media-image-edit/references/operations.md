# Image Edit Operations

Four supported operations. Each maps to a hardcoded fal.ai model.

> **Paths.** Every `scripts/…` path below is relative to this skill's own directory. To actually run one, resolve that directory in the same command — a shell variable does not survive from one call to the next:

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/<the script you want>"
```

> If `$SKILL_DIR` comes back empty, the plugin is running from a checkout rather than an install: use the absolute path from the `Base directory for this skill:` line printed when this skill loaded. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

## style — Style Transfer

Apply an artistic style or visual transformation to an image.

**Model:** `fal-ai/flux/dev/image-to-image`

**Parameters:**
- `--image-url` (required) — source image
- `--prompt` (required) — style description
- `--strength` (optional, default 0.75) — 0.3-0.5 subtle, 0.7-0.9 dramatic

**Example:**
```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/edit-image.sh" \
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
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/edit-image.sh" \
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
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/edit-image.sh" \
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
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
bash "$SKILL_DIR/scripts/edit-image.sh" \
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
