# Screenshot Workflow

## Framework Routing Detection

Read these files to discover all available pages for screenshot candidates.

| Framework | File to Read | What to Look For |
|---|---|---|
| Next.js App Router | `app/` directory structure | Folders with `page.tsx` are routes |
| Next.js Pages Router | `pages/` directory | Each file is a route |
| Rails | `config/routes.rb` | Read entire file for all routes |
| React Router | Search for `createBrowserRouter` or `<Route` | Route definitions with paths |
| Vue Router | `src/router/index.js` or `router.js` | Routes array with path definitions |
| SvelteKit | `src/routes/` directory | Folders with `+page.svelte` are routes |
| Remix | `app/routes/` directory | File-based routing |
| Laravel | `routes/web.php` | Route definitions |
| Django | `urls.py` files | URL patterns |
| Express | Search for `app.get`, `router.get` | Route handlers |

Read the actual files — not just check for existence. Route definitions reveal
what pages are available. Combine with README.md and CHANGELOG.md to understand
which features are worth capturing.

## Common Default URLs

Suggest these when no URL is provided:

- `http://localhost:3000` — Next.js, Create React App, Rails
- `http://localhost:5173` — Vite
- `http://localhost:4000` — Phoenix
- `http://localhost:8080` — Vue CLI, generic

## Advanced Playwright Options

### Element-Focused Screenshot

To capture a specific component instead of the full viewport:

```javascript
const element = await page.locator('[CSS_SELECTOR]');
await element.screenshot({ path: `${SCREENSHOTS_DIR}/element.png` });
```

### Full Page Screenshot

For scrollable content:

```javascript
await page.screenshot({
  path: `${SCREENSHOTS_DIR}/full-page.png`,
  fullPage: true,
});
```

### Dark Mode

```javascript
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: 'dark',
});
```

### Animations Wait

```javascript
await page.waitForTimeout(500); // 500ms settles most CSS transitions
```

### Modal / Hover State

```javascript
await page.click('button.open-modal');
await page.waitForSelector('.modal-content');
await page.screenshot({ path: `${SCREENSHOTS_DIR}/modal.png` });
```

## Verification After Capture

```bash
ls -la screenshots/*.png
sips -g pixelWidth -g pixelHeight screenshots/*.png 2>/dev/null || file screenshots/*.png
```

Expected output for 1440x900 @ 2x: `pixelWidth: 2880`, `pixelHeight: 1800`.

## Error Reference

| Error | Fix |
|---|---|
| Playwright not found | `npm install -D playwright` |
| Page not loading | Check dev server is running |
| Login failed | Inspect login page HTML for correct selectors |
| Element not found | Verify CSS selector; fall back to full-page screenshot |
| Screenshot failed | Check disk space and write permissions to `screenshots/` |
