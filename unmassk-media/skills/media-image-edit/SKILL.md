---
name: media-image-edit
description: >
  Use when the user asks to "edit image", "style transfer", "remove object",
  "change background", "inpaint", "editar imagen", "quitar fondo",
  "apply artistic style", "erase object", "replace background", "fill mask",
  or any instruction-based image editing task using AI.
  Covers style transfer, object removal, background replacement, and inpainting
  via fal.ai API. Uses hardcoded models per operation — no external model search needed.
version: 1.0.0
---

# media-image-edit

AI-powered image editing via fal.ai. Routes each operation to a hardcoded model
optimized for that task.

## Request Routing

| User Request | Operation | Load Reference |
|---|---|---|
| Style transfer, artistic effect | `style` | `references/operations.md` |
| Remove object, erase element | `remove` | `references/operations.md` |
| Change background, replace scene | `background` | `references/operations.md` |
| Inpaint, fill area, mask edit | `inpaint` | `references/operations.md` |
| Which model to use, model info | -- | `references/model-selection.md` |

Load references on-demand. Do not load both at startup.

## Workflow

### Step 1 -- Gather inputs

Collect from the user before running:
- Image URL (required)
- Edit description / prompt (required)
- Operation: `style`, `remove`, `background`, `inpaint` (infer from request)
- Mask URL (required only for `inpaint`)
- Strength 0.0-1.0 (optional, default 0.75; only applies to `style`)

### Step 2 -- Run edit script

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-media/*/skills/media-image-edit' 2>/dev/null | sort -V | tail -1)
bash "$SKILL_DIR/scripts/edit-image.sh" \
  --image-url "<url>" \
  --prompt "<edit description>" \
  --operation <style|remove|background|inpaint> \
  [--mask-url "<mask_url>"] \
  [--strength 0.75]
```

See `references/operations.md` for per-operation parameters and examples.

### Step 3 -- Present result

Display the edited image inline with dimensions and operation label:

```
Here's your edited image:

![Edited Image](<output_url>)

• <width>x<height> | Operation: <operation>
```

## Mandatory Rules

- Always infer the operation from the user's request — do not ask unless ambiguous.
- `inpaint` requires `--mask-url`. If missing, ask the user for it before running.
- `FAL_KEY` must be set. Configure it in `unmassk-media/.env.example` (copy to `.env` and fill `FAL_KEY=`). If still missing at runtime, run with `--add-fal-key` to configure it interactively.
- Do not invent or search for models — they are hardcoded per operation. See `references/model-selection.md`.
- Output the final image URL to the user even if display fails.

## Done Criteria

- Script exits 0
- Output URL is non-empty
- Edited image displayed inline to the user

