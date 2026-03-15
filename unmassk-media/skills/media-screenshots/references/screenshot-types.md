# Screenshot Types

Viewport and format guidance per use case.

## Platform Dimensions

| Platform | Viewport | Scale | Output Size | Notes |
|---|---|---|---|---|
| Product Hunt | 1270x952 | 2x | 2540x1904 | Gallery thumbnails crop to 1270x952 |
| Twitter / X | 1200x675 | 2x | 2400x1350 | 16:9, card preview at 800x418 |
| Instagram (square) | 1080x1080 | 1x | 1080x1080 | No retina advantage — native 1x |
| Instagram (landscape) | 1080x566 | 1x | 1080x566 | 1.91:1 ratio |
| App Store | 1290x2796 | 1x | 1290x2796 | Portrait, mobile frame |
| Documentation | 1280x800 | 2x | 2560x1600 | Readable at inline sizes |
| Landing page / hero | 1440x900 | 2x | 2880x1800 | Default HiDPI; most versatile |

## Playwright Context Per Platform

### Product Hunt
```javascript
const context = await browser.newContext({
  viewport: { width: 1270, height: 952 },
  deviceScaleFactor: 2,
});
```

### Twitter / X
```javascript
const context = await browser.newContext({
  viewport: { width: 1200, height: 675 },
  deviceScaleFactor: 2,
});
```

### Documentation / Hero (default)
```javascript
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
```

## File Naming

Use kebab-case with numeric prefix for sort order:

```
01-dashboard-overview.png
02-analytics.png
03-settings.png
```

## Output Format

Always PNG. Lossy formats (JPEG, WebP) degrade marketing assets and cannot be
losslessly converted back. Compress with `sips` or Squoosh after capture if
file size is a concern — never at capture time.
