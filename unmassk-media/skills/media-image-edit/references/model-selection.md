# Model Selection

## Hardcoded Models

The edit script selects models automatically based on `--operation`. Do not
override these unless explicitly testing a new model.

| Operation | Model | Reason |
|---|---|---|
| `style` | `fal-ai/flux/dev/image-to-image` | FLUX Dev image-to-image, strength-controllable |
| `remove` | `bria/eraser` | Specialized object eraser, works without masks |
| `background` | `fal-ai/flux-pro/kontext` | FLUX Kontext preserves subject identity at edges |
| `inpaint` | `fal-ai/flux-lora-fill` | FLUX LoRA Fill, requires binary mask |

## Searching for Alternative Models on fal.ai

If you need to evaluate newer or alternative models manually:

1. Go to [fal.ai/models](https://fal.ai/models)
2. Search by category (`image-to-image`) or keywords (`inpainting`, `eraser`, `background removal`)
3. Check the model's API schema for required parameters before using it
4. To use an alternative model, call the fal.ai API directly with `curl` or use
   the `mcp__fal-ai__generate` MCP tool if available

## MCP Alternative

If the `mcp__fal-ai__generate` MCP tool is available, you can bypass the script
entirely and call any fal.ai model directly using its `modelId`. Use the script
for the four standard operations; use MCP for experimentation or unlisted models.
