# SEO Thresholds and Quality Gates Reference

On-demand reference for all numeric thresholds, scoring weights, quality gates, and priority taxonomy used in SEO analysis. Consolidates Core Web Vitals thresholds, content minimums, SEO Health Score weights, and issue classification.

---

## Core Web Vitals Thresholds

### Current Metrics

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP (Largest Contentful Paint) | <=2.5s | 2.5s-4.0s | >4.0s |
| INP (Interaction to Next Paint) | <=200ms | 200ms-500ms | >500ms |
| CLS (Cumulative Layout Shift) | <=0.1 | 0.1-0.25 | >0.25 |

**CRITICAL: INP replaced FID on March 12, 2024. FID was fully removed from all Chrome tools (CrUX API, PageSpeed Insights, Lighthouse) on September 9, 2024. NEVER reference FID in any output. INP is the sole interactivity metric.**

Thresholds have remained unchanged since their original definitions. Ignore claims of "tightened thresholds" from SEO blogs.

### Evaluation Method

- Google evaluates at the **75th percentile** of real user data (field data from CrUX)
- 75% of page visits must meet the "good" threshold to pass
- Assessment occurs at both the **page level** and the **origin level**
- Core Web Vitals are a **tiebreaker** ranking signal — they matter most when content quality is similar between competitors
- The December 2025 core update appeared to weight **mobile CWV more heavily**

### Current Pass Rates (October 2025)

| Device | Pass Rate (All 3 CWV) |
|--------|----------------------|
| Desktop | 57.1% |
| Mobile | 49.7% |

### LCP Subparts (February 2025 CrUX Addition)

Break LCP into diagnostic subparts to identify the bottleneck phase:

| Subpart | What It Measures | Target |
|---------|------------------|--------|
| TTFB | Time to First Byte (server response) | <800ms |
| Resource Load Delay | Time from TTFB to LCP resource request start | Minimize |
| Resource Load Time | Time to download the LCP resource | Depends on resource size |
| Element Render Delay | Time from resource loaded to element rendered | Minimize |

**Formula: Total LCP = TTFB + Resource Load Delay + Resource Load Time + Element Render Delay**

Use this breakdown to identify which phase is the primary bottleneck when LCP exceeds the 2.5s threshold.

### Common Bottlenecks by Metric

**LCP bottlenecks:**
- Unoptimized hero images (compress, use WebP/AVIF, add preload)
- Render-blocking CSS/JS (defer, async, critical CSS inlining)
- Slow server response TTFB >200ms (edge CDN, caching)
- Third-party scripts blocking render (defer analytics, chat widgets)
- Web font loading delay (use `font-display: swap` + preload)

**INP bottlenecks:**
- Long JavaScript tasks on main thread (break into <50ms chunks)
- Heavy event handlers (debounce, use `requestAnimationFrame`)
- Excessive DOM size (>1,500 elements concerning, >3,000 critical)
- Third-party scripts hijacking main thread
- Synchronous XHR or localStorage operations
- Layout thrashing (multiple forced reflows)

**CLS bottlenecks:**
- Images/iframes without explicit width and height attributes
- Dynamically injected content above existing content
- Web fonts causing layout shift (use `font-display: swap` + preload)
- Ads/embeds without reserved space (use `min-height` placeholders)
- Late-loading content pushing down the page

### Optimization Priority

1. **LCP** — most impactful for perceived performance
2. **CLS** — most common issue affecting user experience
3. **INP** — matters most for interactive applications

---

## Performance Tooling Updates

| Tool/Feature | Date | Details |
|-------------|------|---------|
| Lighthouse 13.0 | October 2025 | Major audit restructuring, reorganized performance categories, updated scoring weights. Lab tool — always cross-reference with CrUX field data. |
| CrUX Vis | November 2025 | Replaced the old Looker Studio CrUX Dashboard. Use CrUX Vis (`cruxvis.withgoogle.com`) or CrUX API directly. |
| LCP Subparts in CrUX | February 2025 | TTFB, resource load delay, resource load time, element render delay now available as LCP sub-components. |
| Google Search Console updates | December 2025 | AI-powered configuration, branded vs non-branded queries filter, hourly data in API, custom chart annotations, social channels tracking. |
| Soft Navigations API | July 2025 | Chrome 139+ origin trial for SPA CWV measurement. Experimental, no ranking impact yet. |

### Field Data vs Lab Data

| Type | Source | Used for Ranking | Best For |
|------|--------|-----------------|----------|
| Field data | CrUX (real users) | Yes | Ranking assessment, real performance status |
| Lab data | Lighthouse, WebPageTest | No | Debugging, identifying specific bottlenecks |

Always prefer field data (CrUX) for assessing ranking impact. Use lab data (Lighthouse) for diagnosing and debugging specific performance issues.

---

## Content Quality Gates

### Word Count Minimums by Page Type

| Page Type | Min Words | Unique Content % | Notes |
|-----------|-----------|-----------------|-------|
| Homepage | 500 | 100% | Clear value proposition |
| Service / Feature Page | 800 | 100% | Detailed offering explanation |
| Location (Primary) | 600 | 60%+ | City HQ or main service area |
| Location (Secondary) | 500 | 40%+ | Satellite locations |
| Blog Post | 1,500 | 100% | In-depth, valuable content |
| Product Page | 400 | 80%+ | Unique descriptions, specs (300+ simple) |
| Category Page | 400 | 100% | Unique intro, not just listings |
| About Page | 400 | 100% | Company story, team, values |
| Landing Page | 600 | 100% | Focused conversion content |
| FAQ Page | 800 | 100% | Comprehensive Q&A |

These are **topical coverage floors**, not targets. Google has confirmed word count is NOT a direct ranking factor. The goal is comprehensive topical coverage.

### Content Uniqueness Threshold

Minimum 60% unique content across the site. Pages below 60% uniqueness risk duplicate content penalties. For location pages specifically, enforce uniqueness requirements per the thresholds below.

### Location Page Thresholds

| Threshold | Page Count | Action |
|-----------|-----------|--------|
| Warning | 30+ pages | Enforce 60%+ unique content per page |
| Hard Stop | 50+ pages | Require explicit user justification |

**At 30+ pages, each location page must include:**
- Unique local information (landmarks, neighborhoods)
- Location-specific services or offerings
- Local team or staff information
- Genuine customer testimonials from that area

**At 50+ pages, must demonstrate:**
- Legitimate business presence in each location
- Unique content strategy for each page
- Local signals (Google Business Profile, local reviews)

### Doorway Page Detection Signals

Flag pages exhibiting these patterns:
- Only city/state name changed between pages
- No unique local information
- No local business signals
- Keyword-stuffed URLs
- Identical page structure with minimal content variation

---

## Title Tag Thresholds

| Aspect | Minimum | Maximum |
|--------|---------|---------|
| Length | 30 characters | 60 characters |
| Primary keyword | Near the beginning | - |
| Brand name | At end (if included) | - |
| Uniqueness | Each page must have unique title | - |

---

## Meta Description Thresholds

| Aspect | Minimum | Maximum |
|--------|---------|---------|
| Length | 120 characters | 160 characters |
| CTA | Required | - |
| Primary keyword | Include naturally | - |
| Uniqueness | Each page must have unique description | - |

---

## Image Alt Text Thresholds

| Aspect | Minimum | Maximum |
|--------|---------|---------|
| Length | 10 characters | 125 characters |
| Decorative images | `alt=""` or `role="presentation"` | - |
| Content | Describe image content | Not filename or keyword stuffing |

---

## Internal Linking Thresholds

| Page Type | Internal Links Target |
|-----------|----------------------|
| Blog post (1,500+ words) | 5-10 internal links |
| Service page | 3-5 internal links |
| Category page | Links to all child pages |
| Product page | 2-4 internal links |

General guideline: 3-5 relevant internal links per 1,000 words.

---

## Readability Thresholds

| Metric | Target | Notes |
|--------|--------|-------|
| Flesch Reading Ease | 60-70 | General audience. NOT a ranking factor. Quality indicator only. |
| Average sentence length | 15-20 words | - |
| Paragraph length | 2-4 sentences | - |
| Base font size | 16px minimum | Mobile readability |
| Line height | 1.5x font size minimum | Body text |

---

## URL Structure Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| URL length | >100 characters | Flag for review |
| Redirect hops | >1 hop | Fix (max 1 hop allowed) |
| Crawl depth | >3 clicks from homepage | Flag important pages |

---

## Touch Target Thresholds (Mobile)

| Metric | Minimum |
|--------|---------|
| Touch target size | 48x48 CSS pixels |
| Touch target spacing | 8px between targets |

---

## DOM Size Thresholds

| Element Count | Status |
|--------------|--------|
| <1,500 elements | Good |
| 1,500-3,000 elements | Concerning — may affect INP |
| >3,000 elements | Critical — likely causing INP issues |

---

## SEO Health Score Weights

Use these weights to calculate an overall SEO Health Score for a site or page:

| Category | Weight | Description |
|----------|--------|-------------|
| Technical | 22% | Crawlability, indexability, security, URL structure, mobile |
| Content | 23% | E-E-A-T signals, word count, uniqueness, freshness |
| On-Page | 20% | Title tags, meta descriptions, headings, keyword optimization |
| Schema | 10% | Structured data presence, validation, coverage |
| Performance | 10% | Core Web Vitals (LCP, INP, CLS), page speed |
| AI Search | 10% | AI citation readiness, GEO signals, AI crawler access |
| Images | 5% | Alt text, optimization, format, lazy loading |
| **Total** | **100%** | |

### Scoring Scale

| Score Range | Rating | Interpretation |
|-------------|--------|---------------|
| 90-100 | Excellent | Best-in-class SEO implementation |
| 80-89 | Good | Strong foundation, minor improvements available |
| 70-79 | Fair | Functional but missing important optimizations |
| 60-69 | Needs Work | Significant gaps affecting visibility |
| 50-59 | Poor | Major issues requiring immediate attention |
| <50 | Critical | Fundamental problems preventing effective indexing |

---

## E-E-A-T Scoring Weights

| Factor | Weight |
|--------|--------|
| Experience | 20% |
| Expertise | 25% |
| Authoritativeness | 25% |
| Trustworthiness | 30% |

### E-E-A-T Score Interpretation

| Score | Description |
|-------|-------------|
| 90-100 | Exceptional — authority site, recognized expert, full transparency |
| 70-89 | Strong — demonstrated expertise, good trust signals |
| 50-69 | Moderate — some signals, room for improvement |
| 30-49 | Weak — minimal signals, significant gaps |
| 0-29 | Very low — no visible signals, potential trust issues |

---

## Content Freshness Thresholds

| Content Type | Review Frequency |
|--------------|------------------|
| News/current events | Within hours/days |
| Blog posts (evergreen) | Annually |
| Product pages | When specs change |
| Service pages | Quarterly |
| Company info | When changes occur |

Flag content older than 12 months without update for fast-changing topics (technology, finance, health, legal).

---

## Priority Taxonomy

Classify all SEO issues using this taxonomy:

| Priority | Action Timeframe | Examples |
|----------|-----------------|----------|
| Critical | Fix immediately | Noindex on important pages, HTTPS failure, robots.txt blocking Googlebot, broken canonicals, site-wide CWV failure |
| High | Fix this sprint | Missing canonicals, redirect chains, missing sitemap, security header gaps, thin content on key pages, missing schema on product pages |
| Medium | Fix next sprint | URL structure issues, non-critical thin content, missing alt text, IndexNow not implemented, readability below threshold |
| Low | Backlog | Trailing slash inconsistency, URL length warnings, minor redirect optimizations, meta description length, optional schema additions |

### Severity Escalation Rules

- Any issue affecting >50% of indexed pages escalates one level
- Any issue on the homepage or top 10 traffic pages escalates one level
- Security issues (HTTPS, CSP, HSTS) are always minimum High priority
- Issues detected by Google Search Console as errors are always minimum High priority

---

## Safe Programmatic Page Thresholds

### Safe at Scale

| Page Type | Why Safe |
|-----------|----------|
| Integration pages | Real setup documentation, unique technical content |
| Template/tool pages | Downloadable assets, unique functionality |
| Glossary pages | 200+ word unique definitions |
| Product pages | Unique specs, images, reviews |
| User profile pages | User-generated unique content |

### Penalty Risk

| Page Type | Why Risky |
|-----------|-----------|
| Location pages with only city swapped | Duplicate content, doorway pages |
| "Best [tool] for [industry]" at scale | Often thin, no industry-specific value |
| "[Competitor] alternative" at scale | Requires genuine comparison data |
| AI-generated mass content | No unique value, E-E-A-T failure |

---

## File Size and Structure Thresholds

| Metric | Threshold | Notes |
|--------|-----------|-------|
| robots.txt size | <500KB | Google's processing limit |
| XML sitemap (uncompressed) | <50MB | Per sitemaps.org protocol |
| URLs per sitemap file | <50,000 | Use sitemap index for larger sites |
| SSL certificate | TLS 1.2 minimum | TLS 1.0/1.1 are deprecated |
| HSTS max-age | >=31536000 (1 year) | Required for preload list |
| Image alt text | 10-125 characters | Describe content, not filename |

---

## Schema Validation Thresholds

| Check | Requirement |
|-------|-------------|
| @context | Must be `https://schema.org` (not http) |
| @type | Must be valid, non-deprecated |
| Required properties | All present per type |
| URLs | Absolute only (no relative) |
| Dates | ISO 8601 format |
| Placeholder text | None allowed |

---

## Keyword Optimization Thresholds

| Metric | Target |
|--------|--------|
| Keyword density | 1-3% (natural, not forced) |
| Primary keyword placement | Title, H1, first 100 words |
| Semantic variations | Present throughout content |

---

## Mobile-First Indexing Status

Mobile-first indexing is 100% complete as of July 5, 2024. Google crawls and indexes ALL websites exclusively with the mobile Googlebot user-agent. Every threshold and quality gate applies to the mobile version of the site as the primary indexed version.
