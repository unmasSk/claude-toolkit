---
name: media-screenshots
description: >
  Use when the user asks to "screenshot", "take a screenshot", "capture screenshot",
  "product screenshot", "marketing screenshot", "captura de pantalla",
  "screenshot for Product Hunt", "screenshot for social media",
  "screenshot for landing page", "screenshot for documentation",
  "dark mode screenshot", "element screenshot", "screenshot with login",
  or wants to generate screenshots of an app, UI, or web page
  for marketing, Product Hunt, Twitter/X, Instagram, App Store, or documentation.
  Captures true HiDPI (2x retina) screenshots using Playwright.
  Handles authentication, multi-page capture, element focus, dark mode,
  and platform-specific viewport sizing.
  Based on claude-screenshots by Shpigford (MIT License).
version: 1.0.0
---

# media-screenshots -- Marketing Screenshot Generator

Capture HiDPI marketing screenshots of any web app using Playwright.
All screenshots use `deviceScaleFactor: 2` (true retina, 2880x1800 at default viewport).

Based on claude-screenshots by Shpigford (MIT License).

## Request Routing

| User Request | Load Reference |
|---|---|
| Platform sizing (Product Hunt, Twitter, Instagram, App Store) | `references/screenshot-types.md` |
| Framework routing detection, advanced options (dark mode, modals, elements) | `references/workflow.md` |

## Prerequisites

Playwright must be available:

```bash
npx playwright --version 2>/dev/null || npm ls playwright 2>/dev/null | grep playwright
```

If not found, inform the user: `npm install -D playwright`

## Workflow

### Step 1 -- Explore

Read the codebase to understand the app:

1. `README.md` and any subdirectory READMEs -- understand features
2. `CHANGELOG.md` or `HISTORY.md` -- recently added features worth highlighting
3. Routing files to discover available pages -- see `references/workflow.md` for framework-specific files

### Step 2 -- Identify

Build a feature list from exploration:

- Feature name (from README or component name)
- URL path (from routes)
- CSS selector to focus on (if element-specific)
- Required UI state (logged in, modal open, tab selected)

### Step 3 -- Confirm

Ask the user to confirm or modify:

1. App URL (or suggest common defaults from `references/workflow.md`)
2. Screenshot count and purpose (Product Hunt / social media / landing page / docs)
3. Authentication required (yes/no -- if yes, collect login URL, email, password)
4. Feature list -- present discovered features, let user approve or adjust

Load `references/screenshot-types.md` to set the correct viewport for the chosen platform.

### Step 4 -- Generate

```bash
mkdir -p screenshots
```

Copy `${CLAUDE_PLUGIN_ROOT}/skills/media-screenshots/scripts/screenshot-script.mjs` to
the project root, configure `BASE_URL`, `AUTH`, and `SCREENSHOTS`, then run:

```bash
node screenshot-script.mjs
```

Delete the script after capture:

```bash
rm screenshot-script.mjs
```

### Step 5 -- Review

Verify output resolution and summarize:

```bash
ls -la screenshots/*.png
sips -g pixelWidth -g pixelHeight screenshots/*.png 2>/dev/null || identify screenshots/*.png 2>/dev/null || file screenshots/*.png
```

Report: file list, resolution, file sizes, suggested follow-up (dark mode variants,
element-focused crops, platform resizing).

## Mandatory Rules

- Always use `deviceScaleFactor: 2` -- never capture at 1x for marketing use
- Always `waitForLoadState('networkidle')` before capturing -- never screenshot mid-load
- Never hardcode credentials -- use `AUTH` config block in the script
- Naming: kebab-case, numeric prefix (`01-dashboard.png`, `02-analytics.png`)
- Output format: PNG only -- never JPEG or WebP at capture time

## Done Criteria

- All screenshots exist in `screenshots/` with correct resolution
- Script has been deleted from project root
- User has confirmed the screenshots meet their needs

## Reference Files

| File | Load When |
|---|---|
| `references/screenshot-types.md` | Platform dimensions (Product Hunt, Twitter, Instagram, App Store, docs, hero) |
| `references/workflow.md` | Framework routing detection, advanced Playwright options, error reference |
