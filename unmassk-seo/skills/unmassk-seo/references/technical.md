# Technical SEO Reference

On-demand reference for technical SEO audits. Covers 9 categories of technical optimization plus AI crawler management, JavaScript rendering implications, and MCP tool integration.

---

## 1. Crawlability

### robots.txt

Verify robots.txt exists at the domain root and is accessible via HTTP 200. Confirm it does not block critical resources (CSS, JS, images needed for rendering). Validate syntax — malformed directives are silently ignored by crawlers.

**Required checks:**
- File exists and returns HTTP 200
- Does not block Googlebot from critical paths
- References XML sitemap(s) via `Sitemap:` directive
- No wildcard `Disallow: /` for Googlebot or Googlebot-Mobile
- Uses correct user-agent tokens (case-insensitive matching)
- File size under 500KB (Google's processing limit)

**robots.txt optimization rules:**
- Place the most specific user-agent blocks first; crawlers match the most specific block
- Use `Allow:` directives to override broader `Disallow:` rules for specific paths
- Never block `/css/`, `/js/`, or `/images/` from Googlebot — these are needed for rendering
- Use `Crawl-delay:` only for crawlers that respect it (Bing, Yandex — Google ignores it)
- Test changes with Google Search Console's robots.txt tester before deploying

### XML Sitemaps

Verify at least one XML sitemap exists, is referenced in robots.txt, and conforms to the sitemaps.org protocol.

**Required checks:**
- Sitemap exists and returns HTTP 200
- Valid XML format with correct namespace (`xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`)
- Contains only canonical URLs (no redirects, no noindex pages, no 4xx/5xx URLs)
- Under 50MB uncompressed and under 50,000 URLs per file
- Uses sitemap index file for sites exceeding single-file limits
- `<lastmod>` dates are accurate (not all set to the same date)
- Submitted to Google Search Console and Bing Webmaster Tools

### Noindex Tags

Audit all `<meta name="robots" content="noindex">` and `X-Robots-Tag: noindex` header directives. Classify each as intentional or accidental.

**Common accidental noindex sources:**
- Staging environment meta tags left in production
- CMS default settings on new pages
- Plugin or theme conflicts injecting noindex
- Conditional rendering bugs in JavaScript frameworks

### Crawl Depth

Measure click depth from homepage to every indexable page. Flag pages requiring more than 3 clicks from the homepage. For large sites (10,000+ pages), prioritize crawl budget efficiency — ensure high-value pages are within 2 clicks.

**Crawl budget considerations (sites with 10,000+ pages):**
- Identify and eliminate crawl traps (infinite pagination, faceted navigation, calendar pages)
- Use `nofollow` on internal links to low-value pages (login, cart, admin)
- Consolidate parameter URLs with canonical tags or Search Console parameter handling
- Monitor crawl stats in Search Console for anomalies

### AI Crawler Management

AI companies actively crawl the web to train models and power AI search. Managing these crawlers via robots.txt is a critical technical SEO consideration.

**Known AI crawlers (as of 2026):**

| Crawler | Company | robots.txt Token | Purpose |
|---------|---------|-----------------|---------|
| GPTBot | OpenAI | `GPTBot` | Model training |
| ChatGPT-User | OpenAI | `ChatGPT-User` | Real-time browsing |
| ClaudeBot | Anthropic | `ClaudeBot` | Model training |
| PerplexityBot | Perplexity | `PerplexityBot` | Search index + training |
| Bytespider | ByteDance | `Bytespider` | Model training |
| Google-Extended | Google | `Google-Extended` | Gemini training (NOT search) |
| CCBot | Common Crawl | `CCBot` | Open dataset |

**Critical distinctions:**
- Blocking `Google-Extended` prevents Gemini training use but does NOT affect Google Search indexing or AI Overviews (those use `Googlebot`)
- Blocking `GPTBot` prevents OpenAI training but does NOT prevent ChatGPT from citing content via browsing (`ChatGPT-User`)
- Approximately 3-5% of websites currently use AI-specific robots.txt rules

**Selective AI crawler blocking example:**
```
# Allow search indexing, block AI training crawlers
User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Bytespider
Disallow: /

# Allow all other crawlers (including Googlebot for search)
User-agent: *
Allow: /
```

**Strategic recommendation:** Evaluate AI visibility strategy before blocking. Being cited by AI systems drives brand awareness and referral traffic. Cross-reference the AI search / GEO optimization workflow for full AI visibility strategy.

### RSL 1.0 (Really Simple Licensing)

Machine-readable content licensing standard (December 2025) for AI training permissions:
- Backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, Creative Commons
- Allows publishers to specify AI licensing terms in a machine-readable format
- Augments robots.txt for AI-specific permissions
- Implement when clients require granular control over AI training usage

---

## 2. Indexability

### Canonical Tags

Verify every indexable page has a self-referencing canonical tag. Detect conflicts where canonical points to a different URL.

**Required checks:**
- Self-referencing canonical exists on every indexable page
- No conflicts between canonical tag and noindex directive
- Canonical URL matches the actual URL (including protocol, www/non-www, trailing slash)
- No canonical chains (A canonicalizes to B which canonicalizes to C)
- Cross-domain canonicals used only when content is truly duplicated
- Canonical is in the `<head>` section, not the `<body>`

### Duplicate Content

Identify near-duplicate pages caused by parameter URLs, www vs non-www, HTTP vs HTTPS, trailing slashes, and pagination.

**Resolution priority:**
1. 301 redirect all variants to the canonical version
2. Set canonical tags on remaining duplicates
3. Use Search Console parameter handling for query parameters
4. Implement hreflang for multi-language/multi-region duplicates

### Thin Content

Flag pages below minimum word counts per page type (see content reference for thresholds). Thin content wastes crawl budget and dilutes topical authority.

### Pagination

Check for `rel="next"` and `rel="prev"` markup on paginated sequences. Note: Google announced in 2019 that it no longer uses these as indexing signals, but they remain useful for Bing and as semantic indicators.

**Modern pagination best practices:**
- Use self-referencing canonicals on each paginated page (not canonical to page 1)
- Include paginated pages in the XML sitemap
- Provide a "view all" option if feasible for the content volume
- Use load-more or infinite scroll patterns with proper URL handling for JavaScript-rendered pagination

### Hreflang

For multi-language or multi-region sites, validate hreflang implementation:
- Every hreflang tag includes a self-referencing entry
- All hreflang URLs return HTTP 200
- Language codes follow ISO 639-1, region codes follow ISO 3166-1 Alpha-2
- x-default is set for the fallback version
- Hreflang annotations are bidirectional (if page A references B, B must reference A)

### Index Bloat

Identify unnecessary pages consuming crawl budget: tag pages, author archives, date archives, search results pages, empty category pages. Recommend noindex or removal.

---

## 3. Security

### HTTPS Enforcement

Verify HTTPS is enforced site-wide with a valid SSL/TLS certificate. Check for mixed content (HTTP resources loaded on HTTPS pages).

**Required checks:**
- Valid SSL certificate (not expired, correct domain)
- HTTP to HTTPS redirect in place (301, not 302)
- No mixed content warnings (all resources loaded via HTTPS)
- Certificate chain is complete (intermediate certificates included)
- TLS 1.2 minimum (TLS 1.0 and 1.1 are deprecated)

### Security Headers

Audit the following security headers on every response:

| Header | Purpose | Recommended Value |
|--------|---------|-------------------|
| Content-Security-Policy (CSP) | Prevents XSS, data injection | Strict policy appropriate to site |
| Strict-Transport-Security (HSTS) | Forces HTTPS | `max-age=31536000; includeSubDomains; preload` |
| X-Frame-Options | Prevents clickjacking | `DENY` or `SAMEORIGIN` |
| X-Content-Type-Options | Prevents MIME sniffing | `nosniff` |
| Referrer-Policy | Controls referrer information | `strict-origin-when-cross-origin` |
| Permissions-Policy | Controls browser features | Restrict camera, microphone, geolocation |

### HSTS Preload

For high-security sites, check inclusion in the HSTS preload list (hstspreload.org). Requirements: valid certificate, redirect HTTP to HTTPS, serve HSTS header on the HTTPS domain with `includeSubDomains` and `preload` directives, `max-age` of at least 1 year.

---

## 4. URL Structure

### Clean URL Requirements

- Use hyphens as word separators (not underscores)
- Lowercase only
- No query parameters for content pages (use path segments)
- Descriptive keywords in the URL path
- Logical folder hierarchy reflecting site architecture
- No special characters, spaces, or encoded characters

### Redirect Audit

- No redirect chains (max 1 hop from origin to destination)
- Use 301 for permanent moves, 308 for permanent POST redirects
- No redirect loops
- Flag 302 (temporary) redirects that should be 301 (permanent)
- Audit redirect targets — ensure they return HTTP 200

### URL Length

Flag URLs exceeding 100 characters. While there is no hard technical limit, shorter URLs correlate with better crawlability and user experience.

### Trailing Slash Consistency

Pick one convention (with or without trailing slash) and enforce it site-wide via redirects. Inconsistent trailing slash usage creates duplicate content.

---

## 5. Mobile Optimization

### Mobile-First Indexing

Mobile-first indexing is 100% complete as of July 5, 2024. Google now crawls and indexes ALL websites exclusively with the mobile Googlebot user-agent. The desktop version of a site is never the primary indexed version.

**Critical implications:**
- All critical content must be present in the mobile version
- All structured data must be present in the mobile version
- All meta tags (robots, canonical, hreflang) must be present in the mobile version
- Internal links must be accessible and functional on mobile
- Images must have alt text in the mobile version

### Responsive Design Checks

- Viewport meta tag present: `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Responsive CSS media queries properly implemented
- No horizontal scrollbar at any viewport width
- Content readable without zooming

### Touch Target Requirements

- Minimum touch target size: 48x48 CSS pixels
- Minimum spacing between touch targets: 8px
- Applies to buttons, links, form inputs, and all interactive elements
- Verify with Chrome DevTools device emulation

### Font Size

- Minimum base font size: 16px
- Body text legible without zooming on mobile devices
- Line height at least 1.5x the font size for body text

---

## 6. Core Web Vitals

### Current Thresholds (Unchanged Since Original Definitions)

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | <=2.5s | 2.5s-4.0s | >4.0s |
| INP (Interaction to Next Paint) | <=200ms | 200ms-500ms | >500ms |
| CLS (Cumulative Layout Shift) | <=0.1 | 0.1-0.25 | >0.25 |

**CRITICAL: INP replaced FID on March 12, 2024. FID was fully removed from all Chrome tools (CrUX API, PageSpeed Insights, Lighthouse) on September 9, 2024. NEVER reference FID in any output. INP is the sole interactivity metric.**

### Evaluation Method

Google evaluates at the **75th percentile** of real user data (field data from CrUX). 75% of page visits must meet the "good" threshold to pass. Assessment occurs at both the page level and the origin level.

Core Web Vitals are a **tiebreaker** ranking signal — they matter most when content quality is similar between competitors. The December 2025 core update appeared to weight mobile CWV more heavily.

**Current pass rates (October 2025):** 57.1% desktop sites and 49.7% mobile sites pass all three CWV.

### LCP Subparts (February 2025 CrUX Addition)

Break LCP into diagnostic subparts to identify the bottleneck phase:

| Subpart | What It Measures | Target |
|---------|------------------|--------|
| TTFB | Time to First Byte (server response) | <800ms |
| Resource Load Delay | Time from TTFB to LCP resource request start | Minimize |
| Resource Load Time | Time to download the LCP resource | Depends on size |
| Element Render Delay | Time from resource loaded to rendered | Minimize |

**Total LCP = TTFB + Resource Load Delay + Resource Load Time + Element Render Delay**

### Common LCP Bottlenecks

- Unoptimized hero images (compress, use WebP/AVIF, add `<link rel="preload">`)
- Render-blocking CSS/JS (defer, async, critical CSS inlining)
- Slow server response TTFB >200ms (use edge CDN, caching, server-side optimization)
- Third-party scripts blocking render (defer analytics, chat widgets, tag managers)
- Web font loading delay (use `font-display: swap` + preload critical fonts)

### Common INP Bottlenecks

- Long JavaScript tasks on main thread (break into smaller tasks under 50ms)
- Heavy event handlers (debounce, use `requestAnimationFrame`)
- Excessive DOM size (>1,500 elements is concerning, >3,000 is critical)
- Third-party scripts hijacking main thread
- Synchronous XHR or `localStorage` operations
- Layout thrashing (multiple forced reflows in rapid succession)

### Common CLS Bottlenecks

- Images and iframes without explicit `width` and `height` attributes
- Dynamically injected content above existing content (ads, banners, cookie notices)
- Web fonts causing layout shift (use `font-display: swap` + preload)
- Ads and embeds without reserved space (use `min-height` placeholders)
- Late-loading content pushing down the page

### Optimization Priority

1. **LCP** — most impactful for perceived performance
2. **CLS** — most common issue affecting user experience
3. **INP** — matters most for interactive applications (e-commerce, SaaS dashboards)

### Soft Navigations API (Experimental)

Chrome 139+ Origin Trial (July 2025) — first step toward measuring CWV in single-page applications:
- Addresses the long-standing SPA measurement blind spot
- Currently experimental, no ranking impact yet
- Detects "soft navigations" (URL changes without full page load)
- May affect future SPA CWV measurement methodology

**Detection:** Check for SPA frameworks (React, Vue, Angular, Svelte) and warn about current CWV measurement limitations in SPA contexts.

### Measurement Sources

**Field data (what Google uses for ranking):**
- Chrome User Experience Report (CrUX)
- PageSpeed Insights (uses CrUX data)
- Search Console Core Web Vitals report

**Lab data (useful for debugging, not used for ranking):**
- Lighthouse (v13.0 as of October 2025)
- WebPageTest
- Chrome DevTools Performance panel

**CrUX Vis** replaced the CrUX Dashboard (November 2025). The old Looker Studio dashboard was deprecated. Use CrUX Vis at `cruxvis.withgoogle.com` or the CrUX API directly.

---

## 7. Structured Data

### Detection

Scan page source for all structured data formats:
1. JSON-LD: `<script type="application/ld+json">` (preferred format)
2. Microdata: `itemscope`, `itemprop` attributes
3. RDFa: `typeof`, `property` attributes

Always recommend JSON-LD as the primary format — Google's stated preference.

**AI search visibility note:** Content with proper schema has approximately 2.5x higher chance of appearing in AI-generated answers (confirmed by Google and Microsoft, March 2025).

### Validation

For every schema block detected, verify:
1. `@context` is `"https://schema.org"` (not http)
2. `@type` is valid and not deprecated
3. All required properties for the type are present
4. Property values match expected data types
5. No placeholder text remains (e.g., "[Business Name]")
6. URLs are absolute, not relative
7. Dates are in ISO 8601 format
8. Images have valid, accessible URLs

See the schema reference for full type status (active, restricted, deprecated) and the `schema-templates.json` file for ready-to-use JSON-LD templates.

---

## 8. JavaScript Rendering

### CSR vs SSR Implications

Identify whether the site uses client-side rendering (CSR), server-side rendering (SSR), static site generation (SSG), or incremental static regeneration (ISR).

**CSR risks for SEO:**
- Critical content may not be present in the initial HTML response
- Googlebot has a two-wave indexing process: first wave indexes raw HTML, second wave (delayed) renders JavaScript — critical content relying on JS may be indexed late or not at all
- Social media crawlers and many AI crawlers do not execute JavaScript
- Structured data injected via JS may face delayed processing

**SSR/SSG advantages:**
- All content present in the initial HTML response
- Faster indexing, reliable structured data processing
- Better Core Web Vitals (especially LCP and CLS)
- Compatible with all crawlers including social media and AI crawlers

### JavaScript SEO Canonical and Indexing Guidance (December 2025)

Google updated its JavaScript SEO documentation in December 2025 with critical clarifications:

1. **Canonical conflicts:** If a canonical tag in raw HTML differs from one injected by JavaScript, Google may use EITHER one. Ensure canonical tags are identical between server-rendered HTML and JS-rendered output.

2. **noindex with JavaScript:** If raw HTML contains `<meta name="robots" content="noindex">` but JavaScript removes it, Google MAY still honor the noindex from raw HTML. Serve correct robots directives in the initial HTML response.

3. **Non-200 status codes:** Google does NOT render JavaScript on pages returning non-200 HTTP status codes. Any content or meta tags injected via JS on error pages are invisible to Googlebot.

4. **Structured data in JavaScript:** Product, Article, and other structured data injected via JS may face delayed processing. For time-sensitive structured data (especially e-commerce Product markup), include JSON-LD in the initial server-rendered HTML.

**Best practice:** Serve critical SEO elements (canonical, meta robots, structured data, title, meta description) in the initial server-rendered HTML rather than relying on JavaScript injection.

### SPA Framework Detection

Flag single-page application frameworks and their SEO implications:
- **React (Create React App):** CSR by default, recommend Next.js for SSR/SSG
- **Vue (Vite/Vue CLI):** CSR by default, recommend Nuxt for SSR/SSG
- **Angular:** CSR by default, recommend Angular Universal for SSR
- **Svelte:** CSR by default, recommend SvelteKit for SSR/SSG

### Dynamic Rendering

If the site uses dynamic rendering (serving different content to crawlers vs users):
- Verify it is implemented correctly (not cloaking)
- Check that rendered content matches what users see
- Note: Google has stated dynamic rendering is a workaround, not a long-term solution — prefer SSR/SSG

---

## 9. IndexNow Protocol

### Overview

IndexNow is a protocol for instant URL submission to participating search engines. When a page is created, updated, or deleted, notify participating search engines immediately instead of waiting for crawl discovery.

**Supported search engines:**
- Bing
- Yandex
- Naver
- Seznam
- Note: Google does NOT support IndexNow

### Implementation Check

- Verify if the site has an IndexNow API key file at the domain root
- Check CMS plugins (WordPress: IndexNow plugin, Yoast SEO, Rank Math)
- For custom implementations, verify the API endpoint is functional

### When to Recommend

- Sites that publish or update content frequently
- E-commerce sites with inventory changes
- News publishers
- Sites targeting Bing, Yandex, or Naver traffic
- Any site wanting faster indexing on non-Google search engines

---

## MCP Tool Integration

### PageSpeed MCP

If PageSpeed MCP is available, use it for CWV measurements. Provides real-time Lighthouse audits and CrUX field data for any URL. Prefer field data (CrUX) over lab data (Lighthouse) for ranking-relevant performance assessment.

### DataForSEO MCP

If DataForSEO MCP is available, use these endpoints for technical SEO analysis:

| Endpoint | Use Case |
|----------|----------|
| `on_page_instant_pages` | Real page analysis — status codes, page timing, broken links, on-page element checks, redirect chains |
| `on_page_lighthouse` | Lighthouse audits — performance scores, accessibility scores, SEO audit scores, detailed diagnostics |
| `domain_analytics_technologies_domain_technologies` | Technology stack detection — CMS, frameworks, analytics tools, CDN, hosting provider |

**Usage guidance:**
- Use `on_page_instant_pages` as the primary technical analysis tool — it provides comprehensive page-level data including HTTP status, load time, content size, and on-page SEO elements in a single call
- Use `on_page_lighthouse` when detailed performance diagnostics are needed beyond what instant pages provides
- Use `domain_analytics_technologies_domain_technologies` to detect the technology stack, which informs framework-specific SEO recommendations (e.g., React sites need SSR guidance, WordPress sites need plugin-specific advice)

---

## Performance Tooling Updates (2025-2026)

| Tool/Feature | Date | Details |
|-------------|------|---------|
| Lighthouse 13.0 | October 2025 | Major audit restructuring, reorganized performance categories, updated scoring weights. Lab tool only — cross-reference with CrUX field data. |
| CrUX Vis | November 2025 | Replaced the old Looker Studio CrUX Dashboard. Use CrUX Vis or the CrUX API directly. |
| LCP Subparts in CrUX | February 2025 | TTFB, resource load delay, resource load time, element render delay now available as LCP sub-components. |
| Google Search Console updates | December 2025 | AI-powered configuration, branded vs non-branded queries filter, hourly data in API, custom chart annotations, social channels tracking. |
| Soft Navigations API | July 2025 | Chrome 139+ origin trial for SPA CWV measurement. Experimental, no ranking impact. |

---

## Priority Taxonomy

Classify all technical SEO issues using this taxonomy:

| Priority | Action | Examples |
|----------|--------|---------|
| Critical | Fix immediately | Noindex on important pages, site-wide HTTPS failure, robots.txt blocking Googlebot, broken canonical chains |
| High | Fix this sprint | Missing canonical tags, redirect chains, missing XML sitemap, security header gaps |
| Medium | Fix next sprint | URL structure issues, thin content pages, missing alt text, IndexNow not implemented |
| Low | Backlog | Trailing slash inconsistency, URL length warnings, minor redirect optimizations |
