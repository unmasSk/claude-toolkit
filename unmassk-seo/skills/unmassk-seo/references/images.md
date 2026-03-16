# Image Optimization -- SEO & Performance Reference

Reference data for auditing and optimizing images for search engine visibility,
page performance, and accessibility. Load this file when the user requests image
optimization, alt text audit, image SEO analysis, or image performance checks.

---

## Alt Text Requirements

Every `<img>` element must have an `alt` attribute unless the image is purely
decorative (in which case, use `role="presentation"` or `alt=""`).

### Quality Standards

| Criterion | Requirement |
|---|---|
| Presence | Every non-decorative `<img>` must have `alt` text |
| Length | 10-125 characters. Under 10 is likely too vague. Over 125 may be truncated by screen readers and search engines. |
| Content | Describe what the image shows, not what it is. "Professional plumber repairing kitchen sink faucet" is correct. "Image" or "photo.jpg" is not. |
| Keywords | Include relevant keywords where they fit naturally. Do not stuff keywords. |
| Context | Alt text should make sense in the context of the surrounding content. |
| Decorative images | Use `role="presentation"` or `alt=""` for purely decorative images (borders, spacers, background textures). Do not describe decorative images. |

### Good Alt Text Examples

- "Professional plumber repairing kitchen sink faucet"
- "Red 2024 Toyota Camry sedan front view"
- "Team meeting in modern office conference room"
- "Bar chart showing quarterly revenue growth from Q1 to Q4 2025"
- "Step 3: Applying sealant around the window frame"

### Bad Alt Text Examples

| Example | Problem |
|---|---|
| "image.jpg" | Filename, not a description |
| "photo" | Generic, provides no information |
| "plumber plumbing plumber services" | Keyword stuffing |
| "Click here" | Describes action, not image content |
| "" (empty on informative image) | Missing description for meaningful image |
| 200+ character description | Too long, will be truncated |

### Audit Procedure

1. Identify all `<img>` elements on the page.
2. Classify each as informative or decorative.
3. Check informative images for presence and quality of alt text.
4. Check decorative images for `role="presentation"` or `alt=""`.
5. Flag all violations with specific image identifiers (src, position on page).
6. Report missing alt text count, poor alt text count, and compliant count.

---

## File Naming

Image filenames are a ranking signal. Search engines parse filenames to
understand image content.

### Requirements

- **Descriptive:** Use words that describe the image content.
  `blue-running-shoes.webp` is correct. `IMG_1234.jpg` is not.
- **Hyphenated:** Separate words with hyphens. Not underscores, not camelCase.
- **Lowercase:** All characters lowercase. No mixed case.
- **No special characters:** Avoid spaces, accented characters, and symbols.
- **Include relevant keywords:** Where natural. Do not force irrelevant terms.

### Examples

| Bad | Good |
|---|---|
| `IMG_1234.jpg` | `red-toyota-camry-2024-front.webp` |
| `photo (1).png` | `team-meeting-conference-room.webp` |
| `hero_banner_FINAL_v2.jpg` | `homepage-hero-product-showcase.webp` |
| `DSC00142.jpeg` | `kitchen-sink-faucet-repair.webp` |

---

## Image Formats

### Recommended Formats

| Format | Browser Support | Compression | Best For | Recommendation |
|---|---|---|---|---|
| **WebP** | 97%+ global | Excellent lossy and lossless | Default for all web images | Primary recommendation |
| **AVIF** | 92%+ global | Superior compression (30-50% smaller than WebP) | Sites targeting modern browsers | Recommend with WebP fallback |
| **JPEG** | 100% | Good lossy | Fallback for photographs | Use only as fallback |
| **PNG** | 100% | Good lossless | Graphics with transparency, screenshots | Use when transparency required |
| **SVG** | 100% | Vector (scales infinitely) | Icons, logos, illustrations, diagrams | Use for all vector graphics |

### Format Selection Logic

Apply this decision tree when recommending format changes:

1. Is the image a logo, icon, or illustration? Use **SVG**.
2. Does the image require transparency? Use **PNG** (or WebP/AVIF with alpha).
3. Is the image a photograph or complex graphic?
   - Primary: **WebP**
   - Progressive enhancement: **AVIF** with WebP fallback
   - Legacy fallback: **JPEG**

### JPEG XL -- Emerging Format

Google's Chromium team reversed its 2022 removal decision in November 2025 and
announced restoration of JPEG XL support in Chrome using a Rust-based decoder.
The implementation is feature-complete but **not yet in Chrome stable**. JPEG XL
offers lossless JPEG recompression with approximately 20% file size reduction at
zero quality loss, plus competitive lossy compression. Do not recommend JPEG XL
for production web deployment yet. Note it as a format to monitor for future
adoption.

### Picture Element Pattern

Use the `<picture>` element for progressive format enhancement. List the most
efficient format first -- the browser uses the first supported source.

```html
<picture>
  <source srcset="image.avif" type="image/avif">
  <source srcset="image.webp" type="image/webp">
  <img src="image.jpg" alt="Descriptive alt text" width="800" height="600"
       loading="lazy" decoding="async">
</picture>
```

Flag images served as JPEG or PNG without `<picture>` fallback chains as
optimization opportunities. Calculate estimated savings based on typical
WebP compression ratios (25-35% smaller than JPEG, 25-80% smaller than PNG).

---

## File Size Thresholds

### Tiered Thresholds by Image Category

| Image Category | Target | Warning | Critical |
|---|---|---|---|
| Thumbnails (<200px) | < 50 KB | > 100 KB | > 200 KB |
| Content images (200-800px) | < 100 KB | > 200 KB | > 500 KB |
| Hero/banner images (>800px) | < 200 KB | > 300 KB | > 700 KB |

### Audit Procedure

1. Identify all images on the page with their rendered dimensions.
2. Classify each image by category (thumbnail, content, hero/banner).
3. Measure actual file size (from network transfer, not on-disk).
4. Compare against thresholds and assign severity.
5. Sort by file size descending -- largest savings first.
6. Calculate estimated savings for each image (current size minus target).
7. Report total potential savings across all images.

### Compression Recommendations

- Use lossy compression at quality 75-85% for photographs (visually
  imperceptible quality loss at significant size reduction).
- Use lossless compression for graphics, screenshots, and images with text.
- Recommend image CDN services (Cloudflare Images, Imgix, Cloudinary) for
  automatic format negotiation and on-the-fly resizing.
- Flag images that appear to be uncompressed or minimally compressed (file size
  dramatically exceeds expected size for dimensions and format).

---

## Responsive Images

Responsive images serve appropriately sized files to different devices, reducing
bandwidth waste and improving load times.

### srcset Attribute

Use `srcset` with width descriptors to provide multiple image sizes. The browser
selects the best match based on viewport width and device pixel ratio.

```html
<img
  src="image-800.jpg"
  srcset="image-400.jpg 400w, image-800.jpg 800w, image-1200.jpg 1200w"
  sizes="(max-width: 600px) 400px, (max-width: 1200px) 800px, 1200px"
  alt="Descriptive alt text"
  width="800"
  height="600"
>
```

### sizes Attribute

The `sizes` attribute tells the browser the rendered width of the image at each
breakpoint. Without `sizes`, the browser assumes the image is 100vw (full
viewport width), which leads to oversized image downloads on small screens.

Match `sizes` to the actual CSS layout:

| Layout Pattern | sizes Value |
|---|---|
| Full-width image | `100vw` |
| Two-column layout | `(max-width: 768px) 100vw, 50vw` |
| Three-column layout | `(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw` |
| Fixed-width sidebar image | `300px` |
| Content area image | `(max-width: 768px) 100vw, 800px` |

### Audit Checklist

1. Do content images have `srcset` with at least 3 size variants?
2. Do content images have a `sizes` attribute matching the layout?
3. Are the size variants spaced appropriately (not 799w and 800w)?
4. Is the largest variant sufficient for high-DPI displays (2x the rendered
   width)?
5. Is the smallest variant small enough for mobile devices?

Flag images without responsive attributes that are rendered at significantly
different sizes across viewports. Calculate bandwidth waste: if a 1200px image
is served to a 375px mobile viewport, the waste is approximately 70%.

---

## Lazy Loading

Lazy loading defers image downloads until the image is near the viewport,
reducing initial page load time and bandwidth consumption.

### Native Lazy Loading

Use the `loading` attribute on `<img>` elements:

```html
<!-- Below the fold -- lazy load -->
<img src="photo.jpg" loading="lazy" alt="Description"
     width="600" height="400" decoding="async">

<!-- Above the fold / LCP image -- eager load (default) -->
<img src="hero.jpg" alt="Hero description"
     width="1200" height="630" fetchpriority="high">
```

### Rules

| Image Position | loading | fetchpriority | decoding |
|---|---|---|---|
| Above the fold / LCP image | `eager` (default, omit attribute) | `high` | Do not set (let browser optimize) |
| Above the fold / non-LCP | `eager` (default) | Not set | `async` |
| Below the fold | `lazy` | Not set | `async` |

### Critical Rule: Never Lazy-Load LCP Images

Using `loading="lazy"` on the Largest Contentful Paint (LCP) image directly
harms LCP scores. The browser delays fetching the image until it calculates
that the image is near the viewport, adding significant delay to the largest
visible element.

Flag any `loading="lazy"` on the first visible image or hero image as a
**Critical** finding.

### fetchpriority="high" for LCP Images

Add `fetchpriority="high"` to the hero/LCP image to prioritize its download in
the browser's network queue. This tells the browser to fetch this resource
before other images, stylesheets, and non-critical scripts.

```html
<img src="hero.webp" fetchpriority="high" alt="Hero image description"
     width="1200" height="630">
```

Only one image per page should have `fetchpriority="high"` -- the LCP image.
Using it on multiple images negates the benefit.

### decoding="async" for Non-LCP Images

Add `decoding="async"` to non-LCP images to prevent image decoding from
blocking the main thread. This allows the browser to continue rendering other
content while decoding the image in a background thread.

```html
<img src="photo.webp" alt="Description" width="600" height="400"
     loading="lazy" decoding="async">
```

Do not use `decoding="async"` on LCP images -- let the browser optimize decoding
priority for the most critical visual element.

### Audit Checklist

1. Is the LCP/hero image loaded eagerly (no `loading="lazy"`)?
2. Does the LCP image have `fetchpriority="high"`?
3. Do below-fold images have `loading="lazy"`?
4. Do non-LCP images have `decoding="async"`?
5. Is JavaScript-based lazy loading used instead of native? (Flag as
   unnecessary complexity if native is sufficient.)

---

## CLS Prevention

Cumulative Layout Shift (CLS) measures visual stability. Images without
declared dimensions cause layout shifts when they load, pushing content around
and degrading user experience. Google uses CLS as a Core Web Vitals ranking
signal.

### Dimension Requirements

Every `<img>` element must declare its dimensions to allow the browser to
reserve space before the image loads.

**Method 1: HTML attributes (preferred)**

```html
<img src="photo.jpg" width="800" height="600" alt="Description">
```

**Method 2: CSS aspect-ratio**

```html
<img src="photo.jpg" style="aspect-ratio: 4/3; width: 100%;" alt="Description">
```

**Method 3: CSS container with padding-bottom (legacy)**

```html
<div style="position: relative; padding-bottom: 75%; /* 4:3 ratio */">
  <img src="photo.jpg" style="position: absolute; width: 100%; height: 100%;"
       alt="Description">
</div>
```

### Audit Procedure

1. Identify all `<img>` elements.
2. Check for `width` and `height` attributes OR CSS `aspect-ratio`.
3. Flag images with no dimension declaration as **High** severity.
4. Verify that declared dimensions match the actual image aspect ratio (mismatched
   dimensions cause distortion or still cause shifts).
5. Check for responsive images that change aspect ratio across breakpoints
   (these need CSS handling).

### Common CLS Triggers from Images

| Trigger | Fix |
|---|---|
| No width/height attributes | Add width and height matching actual image dimensions |
| CSS `width: 100%` without height constraint | Add `aspect-ratio` or `height: auto` with width/height attributes |
| Dynamically inserted images (JavaScript) | Reserve space with placeholder or skeleton |
| Ad slots adjacent to images | Constrain ad container dimensions |
| Font-dependent image captions | Ensure caption space is reserved |

---

## CDN Usage

### When to Recommend CDN

Recommend CDN-based image delivery for:

- Sites serving more than 20 unique images per page
- Sites with global audience (CDN edge caching reduces latency)
- Sites without existing image optimization pipeline
- Sites serving images from the origin server (same domain, no CDN headers)

### CDN Detection

Check for CDN usage by examining:

1. **Image domain** -- images served from a different domain or subdomain
   (e.g., `images.example.com`, `cdn.example.com`, `example.cloudinary.com`)
2. **Response headers** -- look for CDN-specific headers:
   - `CF-Cache-Status` (Cloudflare)
   - `X-Cache` (CloudFront, Fastly)
   - `X-CDN` (generic)
   - `Via` header with CDN identifiers
3. **Edge caching** -- `Cache-Control` headers with appropriate max-age values
   for static image assets (recommend `max-age=31536000` for versioned images)

### CDN Recommendations

| CDN Type | Examples | Best For |
|---|---|---|
| Image-specific CDN | Cloudinary, Imgix, Cloudflare Images | Automatic format negotiation, on-the-fly resizing, quality optimization |
| General CDN with image features | Cloudflare, CloudFront, Fastly | Sites already using a CDN, need basic image optimization |
| Self-hosted with CDN | Origin + Cloudflare/CloudFront | Sites wanting full control over image pipeline |

Recommend image-specific CDNs for sites that lack an optimization pipeline.
These services automatically serve WebP/AVIF based on browser Accept headers,
resize images to requested dimensions, and apply quality optimization -- solving
multiple audit findings simultaneously.

---

## Output Template

Generate an image audit report with this structure:

### Image Audit Summary

| Metric | Status | Count |
|---|---|---|
| Total Images | -- | XX |
| Missing Alt Text | Flag | XX |
| Poor Alt Text | Flag | XX |
| Oversized Images | Flag | XX |
| Wrong Format (JPEG/PNG without modern fallback) | Flag | XX |
| No Dimensions (CLS risk) | Flag | XX |
| Not Lazy Loaded (below fold) | Flag | XX |
| Missing fetchpriority on LCP | Flag | XX |

### Prioritized Optimization List

Sort by estimated file size savings, largest first:

| Image | Current Size | Format | Issues | Recommended Actions | Est. Savings |
|---|---|---|---|---|---|
| hero.jpg | 450 KB | JPEG | No WebP, no fetchpriority | Convert to WebP, add fetchpriority="high" | ~180 KB |
| ... | ... | ... | ... | ... | ... |

### Total Estimated Savings

Sum all individual savings. Report as absolute (KB/MB) and percentage of
current total image weight.

### Recommendations by Priority

1. **Critical** -- LCP image issues (lazy-loaded hero, missing fetchpriority)
2. **High** -- Missing alt text, oversized images, no dimensions (CLS)
3. **Medium** -- Format conversion opportunities, missing responsive images
4. **Low** -- File naming, CDN adoption, minor compression gains

---

## Script Usage

Use the fetch, parse, screenshot, and visual analysis scripts for image audits.

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <url>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/parse_html.py <file>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/capture_screenshot.py <url>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/analyze_visual.py <file>
```

The parse script extracts all `<img>` elements with their attributes (src, alt,
width, height, loading, decoding, fetchpriority, srcset, sizes). The visual
analysis script identifies above-fold images and LCP candidates. Cross-reference
both outputs to determine which images are LCP candidates and verify they have
correct loading behavior.
